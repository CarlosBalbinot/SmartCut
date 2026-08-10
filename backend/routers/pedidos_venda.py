import uuid
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models.pedido import ItemPedido, PedidoVenda
from models.venda import PrecoReferencia
from schemas.venda_schema import (
    ItemPedidoVendaCreate, ItemPedidoVendaOut,
    PedidoVendaCreate, PedidoVendaOut, PedidoVendaUpdate,
)
from services.pdf_venda_service import (
    gerar_pdf_corte, gerar_pdf_pedido, nome_arquivo_corte, nome_arquivo_pedido,
)
from services.venda_service import (
    get_ou_criar_empresa, get_preco, proximo_numero, recalcular_pedido,
)

router = APIRouter(prefix="/api/v1/pedidos-venda", tags=["pedidos_venda"])


# ── Schemas inline (campos ausentes no venda_schema.py) ──────────────────────

class _PedidoCreate(PedidoVendaCreate):
    tipo: str = "venda"


class _PedidoVendaOut(PedidoVendaOut):
    tipo: str = "venda"
    observacoes: Optional[str] = None


class _PedidoVendaComItensOut(_PedidoVendaOut):
    itens: List[ItemPedidoVendaOut] = []


class _ItemUpdate(BaseModel):
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

@router.get("/proximo-numero")
def get_proximo_numero(tipo: str = "venda", db: Session = Depends(get_db)):
    return {"data": proximo_numero(db, tipo), "error": None}


# ── CRUD pedidos ──────────────────────────────────────────────────────────────

@router.get("/")
def listar(tipo: str | None = None, db: Session = Depends(get_db)):
    q = select(PedidoVenda).order_by(
        PedidoVenda.data_emissao.desc(), PedidoVenda.numero.desc()
    )
    if tipo:
        q = q.where(PedidoVenda.tipo == tipo)
    rows = db.execute(q).scalars().all()
    return {"data": [_PedidoVendaOut.model_validate(r) for r in rows], "error": None}


@router.post("/")
def criar(payload: _PedidoCreate, db: Session = Depends(get_db)):
    numero = proximo_numero(db, payload.tipo)
    pedido = PedidoVenda(numero=numero, **payload.model_dump())
    db.add(pedido)
    db.commit()
    pedido = _load_com_itens(db, pedido.id)
    return {"data": _PedidoVendaComItensOut.model_validate(pedido), "error": None}


@router.get("/{pedido_id}")
def get_one(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    pedido = _load_com_itens(db, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return {"data": _PedidoVendaComItensOut.model_validate(pedido), "error": None}


@router.patch("/{pedido_id}")
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


@router.delete("/{pedido_id}")
def deletar(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    pedido.status = "cancelado"
    db.commit()
    return {"data": None, "error": None}


# ── Itens ─────────────────────────────────────────────────────────────────────

@router.post("/{pedido_id}/itens")
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

    item = ItemPedido(
        pedido_id=pedido_id,
        grupo_id=payload.grupo_id,
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
    )
    db.add(item)
    recalcular_pedido(db, pedido_id)
    db.commit()
    db.refresh(item)
    return {"data": ItemPedidoVendaOut.model_validate(item), "error": None}


@router.patch("/{pedido_id}/itens/{item_id}")
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


@router.delete("/{pedido_id}/itens/{item_id}")
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

@router.get("/{pedido_id}/pdf-pedido")
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


@router.get("/{pedido_id}/pdf-corte")
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

@router.post("/{pedido_id}/gerar-encaixe", status_code=202)
def gerar_encaixe(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return {"data": {"status": "aguardando", "pedido_id": str(pedido_id)}, "error": None}
