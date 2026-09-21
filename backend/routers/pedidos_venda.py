import uuid
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from middleware.permissions import require_permission
from models.pedido import ItemPedido, PedidoVenda, STATUS_VALIDOS
from models.venda import PrecoReferencia
from schemas.venda_schema import (
    ItemPedidoVendaCreate, ItemPedidoVendaOut,
    PedidoVendaCreate, PedidoVendaOut, PedidoVendaUpdate, PedidoStatusUpdate,
)
from services.pdf_venda_service import (
    gerar_pdf_corte, gerar_pdf_pedido, nome_arquivo_corte, nome_arquivo_pedido,
)
from services.venda_service import (
    get_ou_criar_empresa, get_preco, proximo_numero, recalcular_pedido,
)

router = APIRouter(prefix="/api/v1/pedidos-venda", tags=["pedidos_venda"])

_VER = require_permission("pedidos_ver", "ver")
_CRIAR = require_permission("pedidos_criar", "ver")
_EDITAR = require_permission("pedidos_editar", "ver")
_EXCLUIR = require_permission("pedidos_excluir", "ver")


# ── Schemas inline (campos ausentes no venda_schema.py) ──────────────────────

class _PedidoCreate(PedidoVendaCreate):
    tipo: str = "venda"


class _PedidoVendaOut(PedidoVendaOut):
    tipo: str = "venda"


class _PedidoVendaComItensOut(_PedidoVendaOut):
    itens: List[ItemPedidoVendaOut] = []


class _ItemUpdate(BaseModel):
    produto_id: Optional[uuid.UUID] = None
    cor: Optional[str] = None
    lote_id: Optional[uuid.UUID] = None
    qtd_p: Optional[int] = None
    qtd_m: Optional[int] = None
    qtd_g: Optional[int] = None
    qtd_gg: Optional[int] = None
    qtd_g1: Optional[int] = None
    qtd_g2: Optional[int] = None
    qtd_g3: Optional[int] = None
    preco_unitario: Optional[Decimal] = None
    tes_id: Optional[int] = None
    desconto_pct: Optional[Decimal] = None
    desconto_valor: Optional[Decimal] = None
    acrescimo_pct: Optional[Decimal] = None
    acrescimo_valor: Optional[Decimal] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

_ITEM_OPTS = selectinload(PedidoVenda.itens).selectinload(ItemPedido.grupo)


def _load_com_itens(db: Session, pedido_id: uuid.UUID) -> PedidoVenda | None:
    return db.execute(
        select(PedidoVenda).where(PedidoVenda.id == pedido_id).options(_ITEM_OPTS)
    ).scalars().first()


def _itens_com_grupo(db: Session, pedido_id: uuid.UUID):
    return db.execute(
        select(ItemPedido)
        .where(ItemPedido.pedido_id == pedido_id)
        .options(selectinload(ItemPedido.grupo))
        .order_by(ItemPedido.id)
    ).scalars().all()


# ── Número sequencial ─────────────────────────────────────────────────────────

@router.get("/proximo-numero", dependencies=[Depends(_VER)])
def get_proximo_numero(tipo: str = "venda", db: Session = Depends(get_db)):
    return {"data": proximo_numero(db, tipo), "error": None}


# ── CRUD pedidos ──────────────────────────────────────────────────────────────

@router.get("/", dependencies=[Depends(_VER)])
def listar(tipo: str | None = None, db: Session = Depends(get_db)):
    q = select(PedidoVenda).order_by(
        PedidoVenda.data_emissao.desc(), PedidoVenda.numero.desc()
    )
    if tipo:
        q = q.where(PedidoVenda.tipo == tipo)
    rows = db.execute(q).scalars().all()
    return {"data": [_PedidoVendaOut.model_validate(r) for r in rows], "error": None}


@router.post("/", dependencies=[Depends(_CRIAR)])
def criar(payload: _PedidoCreate, db: Session = Depends(get_db)):
    numero = proximo_numero(db, payload.tipo)
    # exclude_unset: campos não enviados ficam de fora do kwargs e caem nos
    # defaults do model (ex.: desconto_geral_pct=0.0) em vez de None, que
    # quebraria colunas NOT NULL.
    pedido = PedidoVenda(numero=numero, **payload.model_dump(exclude_unset=True))
    db.add(pedido)
    db.commit()
    pedido = _load_com_itens(db, pedido.id)
    return {"data": _PedidoVendaComItensOut.model_validate(pedido), "error": None}


@router.get("/{pedido_id}", dependencies=[Depends(_VER)])
def get_one(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    pedido = _load_com_itens(db, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return {"data": _PedidoVendaComItensOut.model_validate(pedido), "error": None}


@router.patch("/{pedido_id}", dependencies=[Depends(_EDITAR)])
def atualizar(
    pedido_id: uuid.UUID, payload: PedidoVendaUpdate, db: Session = Depends(get_db)
):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(pedido, field, val)
    recalcular_pedido(db, pedido_id)
    db.commit()
    pedido = _load_com_itens(db, pedido_id)
    return {"data": _PedidoVendaComItensOut.model_validate(pedido), "error": None}


# Transições permitidas: Aberto -> Fechado, Aberto -> Cancelado,
# Fechado -> Aberto (só se ainda não tem NF-e emitida). Fechado -> Cancelado
# e qualquer transição a partir de Cancelado não são permitidas.
def _validar_transicao_status(atual: str, novo: str, nfe_id: int | None) -> None:
    if novo not in STATUS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Status inválido: {novo}")
    if atual == novo:
        raise HTTPException(status_code=400, detail="O pedido já está neste status.")
    if atual == "Aberto" and novo in ("Fechado", "Cancelado"):
        return
    if atual == "Fechado" and novo == "Aberto":
        if nfe_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Não é possível reabrir um pedido com NF-e emitida.",
            )
        return
    raise HTTPException(
        status_code=400, detail=f"Transição de {atual} para {novo} não permitida."
    )


@router.patch("/{pedido_id}/status", dependencies=[Depends(_EDITAR)])
def alterar_status(
    pedido_id: uuid.UUID, payload: PedidoStatusUpdate, db: Session = Depends(get_db)
):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    _validar_transicao_status(pedido.status, payload.status, pedido.nfe_id)
    pedido.status = payload.status
    db.commit()
    pedido = _load_com_itens(db, pedido_id)
    return {"data": _PedidoVendaComItensOut.model_validate(pedido), "error": None}


@router.delete("/{pedido_id}", dependencies=[Depends(_EXCLUIR)])
def deletar(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    """Soft delete — mantido por compatibilidade. O fluxo novo usa
    PATCH /{pedido_id}/status com {"status": "Cancelado"} (botão
    "Cancelar Pedido" no frontend)."""
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    pedido.status = "Cancelado"
    db.commit()
    return {"data": None, "error": None}


# ── Itens ─────────────────────────────────────────────────────────────────────

@router.post("/{pedido_id}/itens", dependencies=[Depends(_EDITAR)])
def adicionar_item(
    pedido_id: uuid.UUID,
    payload: ItemPedidoVendaCreate,
    db: Session = Depends(get_db),
):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    preco_unit = payload.preco_unitario
    if preco_unit is None and pedido.tabela_preco_id:
        preco_unit = get_preco(
            payload.grupo_id, pedido.tabela_preco_id, pedido.condicoes or "", db
        )

    total_qty = (
        (payload.qtd_p or 0) + (payload.qtd_m or 0) + (payload.qtd_g or 0)
        + (payload.qtd_gg or 0) + (payload.qtd_g1 or 0) + (payload.qtd_g2 or 0)
        + (payload.qtd_g3 or 0)
    )
    preco_total = (
        Decimal(str(preco_unit)) * total_qty if preco_unit is not None else Decimal("0")
    )

    # TES do item: usa o que veio explícito no payload; senão cai para o
    # TES padrão do cabeçalho do pedido. A regra pedida ("TES do produto
    # tem prioridade") não é implementável hoje — ItemPedido.grupo_id
    # aponta para GrupoMolde (catálogo de corte), não para o cadastro
    # Produto que tem tes_saida_id; as duas tabelas não têm vínculo entre
    # si (isso é o que a Fase 3, ainda não feita, deveria resolver).
    tes_id = payload.tes_id if payload.tes_id is not None else pedido.tes_id

    item = ItemPedido(
        pedido_id=pedido_id,
        grupo_id=payload.grupo_id,
        produto_id=payload.produto_id,
        cor=payload.cor,
        qtd_p=payload.qtd_p or 0,
        qtd_m=payload.qtd_m or 0,
        qtd_g=payload.qtd_g or 0,
        qtd_gg=payload.qtd_gg or 0,
        qtd_g1=payload.qtd_g1 or 0,
        qtd_g2=payload.qtd_g2 or 0,
        qtd_g3=payload.qtd_g3 or 0,
        preco_unitario=preco_unit or Decimal("0"),
        preco_total=preco_total,
        tes_id=tes_id,
        desconto_pct=payload.desconto_pct,
        desconto_valor=payload.desconto_valor,
        acrescimo_pct=payload.acrescimo_pct,
        acrescimo_valor=payload.acrescimo_valor,
    )
    db.add(item)
    # flush obrigatório: a sessão roda com autoflush=False (database.py), e
    # recalcular_pedido faz um SELECT novo em itens_pedido — sem o flush,
    # esse item recém-criado fica invisível para o próprio recálculo do
    # total desta mesma requisição (bug pré-existente, só ficou visível
    # agora que o total passou a depender de desconto/frete também).
    db.flush()
    recalcular_pedido(db, pedido_id)
    db.commit()
    db.refresh(item)
    return {"data": ItemPedidoVendaOut.model_validate(item), "error": None}


@router.patch("/{pedido_id}/itens/{item_id}", dependencies=[Depends(_EDITAR)])
def editar_item(
    pedido_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: _ItemUpdate,
    db: Session = Depends(get_db),
):
    item = db.execute(
        select(ItemPedido).where(
            ItemPedido.id == item_id,
            ItemPedido.pedido_id == pedido_id,
        )
    ).scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, val)

    if item.preco_unitario is not None:
        total_qty = (
            (item.qtd_p or 0) + (item.qtd_m or 0) + (item.qtd_g or 0)
            + (item.qtd_gg or 0) + (item.qtd_g1 or 0) + (item.qtd_g2 or 0)
            + (item.qtd_g3 or 0)
        )
        item.preco_total = Decimal(str(item.preco_unitario)) * total_qty

    recalcular_pedido(db, pedido_id)
    db.commit()
    db.refresh(item)
    return {"data": ItemPedidoVendaOut.model_validate(item), "error": None}


@router.delete("/{pedido_id}/itens/{item_id}", dependencies=[Depends(_EDITAR)])
def remover_item(
    pedido_id: uuid.UUID, item_id: uuid.UUID, db: Session = Depends(get_db)
):
    item = db.execute(
        select(ItemPedido).where(
            ItemPedido.id == item_id,
            ItemPedido.pedido_id == pedido_id,
        )
    ).scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    db.delete(item)
    recalcular_pedido(db, pedido_id)
    db.commit()
    return {"data": None, "error": None}


# ── PDFs ──────────────────────────────────────────────────────────────────────

@router.get("/{pedido_id}/pdf-pedido", dependencies=[Depends(_VER)])
def pdf_pedido(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    itens = _itens_com_grupo(db, pedido_id)
    empresa = get_ou_criar_empresa(db)

    precos_ref = {}
    if pedido.tabela_preco_id and itens:
        grupo_ids = {item.grupo_id for item in itens}
        refs = db.execute(
            select(PrecoReferencia).where(
                PrecoReferencia.tabela_id == pedido.tabela_preco_id,
                PrecoReferencia.grupo_id.in_(grupo_ids),
            )
        ).scalars().all()
        precos_ref = {str(r.grupo_id): r for r in refs}

    pdf_bytes = gerar_pdf_pedido(pedido, itens, empresa, precos_ref)
    filename = nome_arquivo_pedido(pedido)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


@router.get("/{pedido_id}/pdf-corte", dependencies=[Depends(_VER)])
def pdf_corte(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    itens = _itens_com_grupo(db, pedido_id)
    pdf_bytes = gerar_pdf_corte(pedido, itens)
    filename = nome_arquivo_corte(pedido)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


# ── Encaixe (placeholder) ─────────────────────────────────────────────────────

@router.post("/{pedido_id}/gerar-encaixe", status_code=202, dependencies=[Depends(_EDITAR)])
def gerar_encaixe(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return {"data": {"status": "aguardando", "pedido_id": str(pedido_id)}, "error": None}
