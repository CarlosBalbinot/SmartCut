import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from models.painel_vendedor import MetaVendedor, Usuario
from models.pedido import PedidoVenda
from models.venda import TabelaPreco, Vendedor, VendedorTabelaComissao
from schemas.venda_schema import (
    PedidoVendaOut, VendedorCreate, VendedorOut, VendedorUpdate,
)
from services.auth_service import hash_senha, validar_politica_senha

router = APIRouter(prefix="/api/v1/vendedores", tags=["vendedores"])

_MOD = "cadastros_vendedores"


# ── Schemas inline (campos ausentes no venda_schema.py) ──────────────────────

class _VendedorCreate(VendedorCreate):
    comissao_padrao_pct: Optional[Decimal] = Field(None, ge=0, le=100)


class _VendedorUpdate(VendedorUpdate):
    comissao_padrao_pct: Optional[Decimal] = Field(None, ge=0, le=100)


class _VendedorOut(VendedorOut):
    comissao_padrao_pct: Optional[Decimal] = None


class _ComissaoTabelaIn(BaseModel):
    tabela_preco_id: uuid.UUID
    comissao_pct: Decimal = Field(..., ge=0, le=100)


def _proximo_codigo(db: Session) -> str:
    codigos = [
        row[0] for row in
        db.execute(select(Vendedor.codigo).where(Vendedor.codigo.isnot(None))).all()
    ]
    max_val = 0
    for codigo in codigos:
        try:
            n = int(codigo)
            if n > max_val:
                max_val = n
        except (ValueError, TypeError):
            pass
    return str(max_val + 1).zfill(4)


@router.get("/", dependencies=[Depends(require_permission(_MOD, "ver"))])
def listar(busca: str = "", status: str | None = None, db: Session = Depends(get_db)):
    q = select(Vendedor)
    if status:
        q = q.where(Vendedor.status == status)
    if busca:
        termo = f"%{busca}%"
        q = q.where(Vendedor.nome.ilike(termo) | Vendedor.cpf_cnpj.ilike(termo))
    rows = db.execute(q.order_by(Vendedor.nome)).scalars().all()
    return {"data": [_VendedorOut.model_validate(r) for r in rows], "error": None}


@router.post("/", dependencies=[Depends(require_permission(_MOD, "criar"))])
def criar(payload: _VendedorCreate, db: Session = Depends(get_db)):
    v = Vendedor(codigo=_proximo_codigo(db), **payload.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return {"data": _VendedorOut.model_validate(v), "error": None}


@router.get("/{vendedor_id}", dependencies=[Depends(require_permission(_MOD, "ver"))])
def get_one(vendedor_id: uuid.UUID, db: Session = Depends(get_db)):
    v = db.get(Vendedor, vendedor_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vendedor não encontrado")
    return {"data": _VendedorOut.model_validate(v), "error": None}


@router.patch("/{vendedor_id}", dependencies=[Depends(require_permission(_MOD, "editar"))])
def atualizar(vendedor_id: uuid.UUID, payload: _VendedorUpdate, db: Session = Depends(get_db)):
    v = db.get(Vendedor, vendedor_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vendedor não encontrado")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(v, field, val)
    db.commit()
    db.refresh(v)
    return {"data": _VendedorOut.model_validate(v), "error": None}


@router.delete("/{vendedor_id}", dependencies=[Depends(require_permission(_MOD, "excluir"))])
def deletar(vendedor_id: uuid.UUID, db: Session = Depends(get_db)):
    v = db.get(Vendedor, vendedor_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vendedor não encontrado")
    v.ativo = False
    db.commit()
    return {"data": None, "error": None}


# ── Comissão por tabela de preço (VendedorTabelaComissao) ───────────────────
# Tem prioridade sobre comissao_padrao_pct — ver venda_service.resolver_comissao.

def _get_vendedor(db: Session, vendedor_id: uuid.UUID) -> Vendedor:
    v = db.get(Vendedor, vendedor_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vendedor não encontrado")
    return v


def _listar_comissoes(db: Session, vendedor_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(VendedorTabelaComissao, TabelaPreco)
        .join(TabelaPreco, VendedorTabelaComissao.tabela_preco_id == TabelaPreco.id)
        .where(VendedorTabelaComissao.vendedor_id == vendedor_id)
        .order_by(TabelaPreco.nome)
    ).all()
    return [
        {
            "id": c.id,
            "tabela_preco_id": c.tabela_preco_id,
            "tabela_nome": t.nome,
            "tabela_ativa": t.ativa,
            "comissao_pct": c.comissao_pct,
        }
        for c, t in rows
    ]


@router.get("/{vendedor_id}/comissoes", dependencies=[Depends(require_permission(_MOD, "ver"))])
def listar_comissoes(vendedor_id: uuid.UUID, db: Session = Depends(get_db)):
    _get_vendedor(db, vendedor_id)
    return {"data": _listar_comissoes(db, vendedor_id), "error": None}


@router.put("/{vendedor_id}/comissoes", dependencies=[Depends(require_permission(_MOD, "editar"))])
def upsert_comissoes(
    vendedor_id: uuid.UUID,
    payload: List[_ComissaoTabelaIn] = Body(...),
    db: Session = Depends(get_db),
):
    """Upsert em lote — tudo ou nada: qualquer linha inválida recusa o lote.
    Tabelas fora do lote mantêm o vínculo atual."""
    _get_vendedor(db, vendedor_id)

    vistas: set[uuid.UUID] = set()
    for idx, linha in enumerate(payload, start=1):
        if linha.tabela_preco_id in vistas:
            raise HTTPException(status_code=422, detail=f"Linha {idx}: tabela de preço repetida no lote.")
        vistas.add(linha.tabela_preco_id)
        if not db.get(TabelaPreco, linha.tabela_preco_id):
            raise HTTPException(status_code=422, detail=f"Linha {idx}: tabela de preço não encontrada.")

    existentes = {
        c.tabela_preco_id: c
        for c in db.execute(
            select(VendedorTabelaComissao).where(VendedorTabelaComissao.vendedor_id == vendedor_id)
        ).scalars().all()
    }
    for linha in payload:
        registro = existentes.get(linha.tabela_preco_id)
        if registro is None:
            db.add(VendedorTabelaComissao(
                vendedor_id=vendedor_id,
                tabela_preco_id=linha.tabela_preco_id,
                comissao_pct=linha.comissao_pct,
            ))
        else:
            registro.comissao_pct = linha.comissao_pct

    db.commit()
    return {"data": _listar_comissoes(db, vendedor_id), "error": None}


@router.delete(
    "/{vendedor_id}/comissoes/{comissao_id}",
    dependencies=[Depends(require_permission(_MOD, "editar"))],
)
def remover_comissao(vendedor_id: uuid.UUID, comissao_id: uuid.UUID, db: Session = Depends(get_db)):
    registro = db.get(VendedorTabelaComissao, comissao_id)
    if not registro or registro.vendedor_id != vendedor_id:
        raise HTTPException(status_code=404, detail="Comissão não encontrada")
    db.delete(registro)
    db.commit()
    return {"data": None, "error": None}


class CredenciaisInput(BaseModel):
    username: str
    senha: str


class MetasInput(BaseModel):
    meta_ativacao: Optional[float] = None
    bonus_logistica: Optional[float] = None
    meta_novos_clientes: Optional[int] = None
    bonus_expansao: Optional[float] = None
    pedido_minimo: Optional[float] = None


@router.get("/{vendedor_id}/credenciais", dependencies=[Depends(require_permission(_MOD, "ver"))])
def get_credenciais(vendedor_id: uuid.UUID, db: Session = Depends(get_db)):
    v = db.get(Vendedor, vendedor_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vendedor não encontrado")
    usuario = db.execute(select(Usuario).where(Usuario.vendedor_id == vendedor_id)).scalar_one_or_none()
    return {
        "data": {"username": usuario.username if usuario else None, "tem_acesso": usuario is not None},
        "error": None,
    }


@router.post("/{vendedor_id}/credenciais", dependencies=[Depends(require_permission(_MOD, "editar"))])
def set_credenciais(vendedor_id: uuid.UUID, payload: CredenciaisInput, db: Session = Depends(get_db)):
    v = db.get(Vendedor, vendedor_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vendedor não encontrado")

    # Item 1.3: política mínima de senha nas credenciais do vendedor.
    msg = validar_politica_senha(payload.senha)
    if msg:
        raise HTTPException(status_code=400, detail=msg)

    usuario = db.execute(select(Usuario).where(Usuario.vendedor_id == vendedor_id)).scalar_one_or_none()
    if usuario:
        usuario.username = payload.username
        usuario.senha_hash = hash_senha(payload.senha)
    else:
        usuario = Usuario(vendedor_id=vendedor_id, username=payload.username, senha_hash=hash_senha(payload.senha))
        db.add(usuario)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username já existe.")
    return {"data": {"username": usuario.username}, "error": None}


@router.get("/{vendedor_id}/metas", dependencies=[Depends(require_permission(_MOD, "ver"))])
def get_metas(vendedor_id: uuid.UUID, db: Session = Depends(get_db)):
    v = db.get(Vendedor, vendedor_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vendedor não encontrado")
    meta = db.execute(select(MetaVendedor).where(MetaVendedor.vendedor_id == vendedor_id)).scalar_one_or_none()
    if not meta:
        meta = MetaVendedor(vendedor_id=vendedor_id)
        db.add(meta)
        db.commit()
        db.refresh(meta)
    return {
        "data": {
            "meta_ativacao": float(meta.meta_ativacao),
            "bonus_logistica": float(meta.bonus_logistica),
            "meta_novos_clientes": meta.meta_novos_clientes,
            "bonus_expansao": float(meta.bonus_expansao),
            "pedido_minimo": float(meta.pedido_minimo),
        },
        "error": None,
    }


@router.patch("/{vendedor_id}/metas", dependencies=[Depends(require_permission(_MOD, "editar"))])
def update_metas(vendedor_id: uuid.UUID, payload: MetasInput, db: Session = Depends(get_db)):
    v = db.get(Vendedor, vendedor_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vendedor não encontrado")
    meta = db.execute(select(MetaVendedor).where(MetaVendedor.vendedor_id == vendedor_id)).scalar_one_or_none()
    if not meta:
        meta = MetaVendedor(vendedor_id=vendedor_id)
        db.add(meta)
    for field, val in payload.model_dump(exclude_unset=True).items():
        if val is not None:
            setattr(meta, field, val)
    db.commit()
    db.refresh(meta)
    return {
        "data": {
            "meta_ativacao": float(meta.meta_ativacao),
            "bonus_logistica": float(meta.bonus_logistica),
            "meta_novos_clientes": meta.meta_novos_clientes,
            "bonus_expansao": float(meta.bonus_expansao),
            "pedido_minimo": float(meta.pedido_minimo),
        },
        "error": None,
    }


@router.get("/{vendedor_id}/dashboard", dependencies=[Depends(require_permission(_MOD, "ver"))])
def dashboard(vendedor_id: uuid.UUID, db: Session = Depends(get_db)):
    v = db.get(Vendedor, vendedor_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vendedor não encontrado")

    hoje = date.today()
    mes_inicio = hoje.replace(day=1)
    seis_meses_atras = (mes_inicio - timedelta(days=1)).replace(day=1)
    for _ in range(5):
        seis_meses_atras = (seis_meses_atras - timedelta(days=1)).replace(day=1)

    pedidos_mes = db.execute(
        select(PedidoVenda).where(
            PedidoVenda.vendedor_id == vendedor_id,
            PedidoVenda.data_emissao >= mes_inicio,
            PedidoVenda.status != "cancelado",
        )
    ).scalars().all()

    pedidos_6m = db.execute(
        select(PedidoVenda).where(
            PedidoVenda.vendedor_id == vendedor_id,
            PedidoVenda.data_emissao >= seis_meses_atras,
            PedidoVenda.status != "cancelado",
        ).order_by(PedidoVenda.data_emissao)
    ).scalars().all()

    total_mes = sum(float(p.total_pedido or 0) for p in pedidos_mes)
    num_pedidos_mes = len(pedidos_mes)
    comissao_mes = sum(float(p.comissao_valor or 0) for p in pedidos_mes)
    ticket_medio = total_mes / num_pedidos_mes if num_pedidos_mes > 0 else 0.0

    por_mes: dict = defaultdict(lambda: {"total": 0.0, "num_pedidos": 0})
    for p in pedidos_6m:
        chave = p.data_emissao.strftime("%Y-%m")
        por_mes[chave]["total"] += float(p.total_pedido or 0)
        por_mes[chave]["num_pedidos"] += 1

    vendas_ultimos_6_meses = [
        {"mes": k, "total": v["total"], "num_pedidos": v["num_pedidos"]}
        for k, v in sorted(por_mes.items())
    ]

    return {
        "data": {
            "total_mes": total_mes,
            "num_pedidos_mes": num_pedidos_mes,
            "comissao_mes": comissao_mes,
            "ticket_medio": ticket_medio,
            "vendas_ultimos_6_meses": vendas_ultimos_6_meses,
            "pedidos_do_mes": [PedidoVendaOut.model_validate(p) for p in pedidos_mes],
        },
        "error": None,
    }
