import math
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, extract, or_
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_vendedor_atual
from models.painel_vendedor import Catalogo, CatalogoVendedor, Lead, MetaVendedor
from models.pedido import PedidoVenda
from models.venda import TabelaPreco, Vendedor

router = APIRouter(prefix="/api/v1/vendedor", tags=["vendedor-painel"])


def _get_vendedor(db: Session, vendedor_id: str) -> Vendedor:
    v = db.get(Vendedor, uuid.UUID(vendedor_id))
    if not v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendedor não encontrado")
    return v


def _comissao_pedido(p: PedidoVenda, db: Session, cache: dict) -> Decimal:
    if not p.tabela_preco_id:
        return Decimal("0")
    if p.tabela_preco_id not in cache:
        cache[p.tabela_preco_id] = db.get(TabelaPreco, p.tabela_preco_id)
    tabela = cache[p.tabela_preco_id]
    return (p.total_pedido * tabela.comissao_pct) if tabela else Decimal("0")


@router.get("/perfil")
def perfil(
    vendedor_id: str = Depends(get_vendedor_atual),
    db: Session = Depends(get_db),
):
    v = _get_vendedor(db, vendedor_id)
    return {"data": {"nome": v.nome, "vendedor_nome": v.nome, "name": v.nome, "telefone": v.telefone, "email": v.email}, "error": None}


@router.get("/dashboard")
def dashboard(
    vendedor_id: str = Depends(get_vendedor_atual),
    db: Session = Depends(get_db),
):
    v = _get_vendedor(db, vendedor_id)
    now = datetime.now(timezone.utc)

    pedidos_mes = (
        db.query(PedidoVenda)
        .filter(
            PedidoVenda.vendedor_id == v.id,
            PedidoVenda.status.in_(["confirmado", "entregue"]),
            extract("month", PedidoVenda.data_emissao) == now.month,
            extract("year", PedidoVenda.data_emissao) == now.year,
        )
        .all()
    )

    total_vendido_mes = sum((p.total_pedido for p in pedidos_mes), Decimal("0"))
    num_pedidos_mes = len(pedidos_mes)
    ticket_medio = (total_vendido_mes / num_pedidos_mes) if num_pedidos_mes else Decimal("0")

    cache: dict = {}
    comissao_mes = sum((_comissao_pedido(p, db, cache) for p in pedidos_mes), Decimal("0"))

    clientes_mes = {p.cliente_razao_social for p in pedidos_mes}
    clientes_anteriores = {
        r.cliente_razao_social
        for r in db.query(PedidoVenda.cliente_razao_social)
        .filter(
            PedidoVenda.representante == v.nome,
            or_(
                extract("year", PedidoVenda.data_emissao) < now.year,
                and_(
                    extract("year", PedidoVenda.data_emissao) == now.year,
                    extract("month", PedidoVenda.data_emissao) < now.month,
                ),
            ),
        )
        .all()
    }
    novos_clientes_mes = len(clientes_mes - clientes_anteriores)

    meta = db.query(MetaVendedor).filter(MetaVendedor.vendedor_id == v.id).first()
    if not meta:
        meta = MetaVendedor(vendedor_id=v.id)

    ultimos_3 = (
        db.query(PedidoVenda)
        .filter(PedidoVenda.vendedor_id == v.id)
        .order_by(PedidoVenda.data_emissao.desc())
        .limit(3)
        .all()
    )

    return {
        "total_vendido_mes": total_vendido_mes,
        "num_pedidos_mes": num_pedidos_mes,
        "comissao_mes": comissao_mes,
        "ticket_medio": ticket_medio,
        "novos_clientes_mes": novos_clientes_mes,
        "meta": {
            "meta_ativacao": meta.meta_ativacao,
            "bonus_logistica": meta.bonus_logistica,
            "meta_novos_clientes": meta.meta_novos_clientes,
            "bonus_expansao": meta.bonus_expansao,
            "pedido_minimo": meta.pedido_minimo,
        },
        "bonus_logistica_atingido": total_vendido_mes >= meta.meta_ativacao,
        "bonus_expansao_quantidade": (
            math.floor(novos_clientes_mes / meta.meta_novos_clientes)
            if meta.meta_novos_clientes
            else 0
        ),
        "ultimos_3_pedidos": [
            {"numero": p.numero, "cliente": p.cliente_razao_social, "total": p.total_pedido, "status": p.status}
            for p in ultimos_3
        ],
    }


@router.get("/catalogos")
def listar_catalogos(
    vendedor_id: str = Depends(get_vendedor_atual),
    db: Session = Depends(get_db),
):
    v = _get_vendedor(db, vendedor_id)
    rows = (
        db.query(Catalogo, TabelaPreco.nome.label("tabela_nome"))
        .join(CatalogoVendedor, CatalogoVendedor.catalogo_id == Catalogo.id)
        .outerjoin(TabelaPreco, TabelaPreco.id == Catalogo.tabela_preco_id)
        .filter(CatalogoVendedor.vendedor_id == v.id, Catalogo.ativo == True)
        .all()
    )
    
    catalogos = [
        {
            "id": str(cat.id),
            "nome": cat.nome,
            "tabela_preco_nome": tabela_nome,
            "arquivo_path": cat.arquivo_path,
        }
        for cat, tabela_nome in rows
    ]
    return {"data": catalogos, "error": None}


@router.get("/catalogos/{catalogo_id}/download")
def download_catalogo(
    catalogo_id: uuid.UUID,
    vendedor_id: str = Depends(get_vendedor_atual),
    db: Session = Depends(get_db),
):
    v = _get_vendedor(db, vendedor_id)
    acesso = (
        db.query(CatalogoVendedor)
        .filter(
            CatalogoVendedor.catalogo_id == catalogo_id,
            CatalogoVendedor.vendedor_id == v.id,
        )
        .first()
    )
    if not acesso:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a este catálogo")

    cat = db.get(Catalogo, catalogo_id)
    if not cat or not cat.ativo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catálogo não encontrado")

    if not os.path.isfile(cat.arquivo_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo não encontrado no servidor")

    filename = os.path.basename(cat.arquivo_path)

    def _stream():
        with open(cat.arquivo_path, "rb") as f:
            yield from f

    return StreamingResponse(
        _stream(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pedidos")
def listar_pedidos(
    vendedor_id: str = Depends(get_vendedor_atual),
    db: Session = Depends(get_db),
):
    v = _get_vendedor(db, vendedor_id)
    pedidos = (
        db.query(PedidoVenda)
        .filter(PedidoVenda.vendedor_id == v.id)
        .order_by(PedidoVenda.data_emissao.desc())
        .all()
    )
    cache: dict = {}

    data_pedidos = [
        {
            "numero": p.numero,
            "data": p.data_emissao,
            "cliente": p.cliente_razao_social,
            "total": float(p.total_pedido), 
            "comissao": float(_comissao_pedido(p, db, cache)),
            "status": p.status,
        }
        for p in pedidos
    ]
    return {"data": data_pedidos, "error": None}


@router.get("/leads")
def listar_leads(
    vendedor_id: str = Depends(get_vendedor_atual),
    db: Session = Depends(get_db),
):
    v = _get_vendedor(db, vendedor_id)
    leads = (
        db.query(Lead)
        .filter(Lead.vendedor_id == v.id)
        .order_by(Lead.criado_em.desc())
        .all()
    )
    data_leads = [
        {
            "id": str(lead.id),
            "nome": lead.nome,
            "segmento": lead.segmento,
            "endereco": lead.endereco,
            "cidade": lead.cidade,
            "telefone": lead.telefone,
            "observacao": lead.observacao,
            "status": lead.status,
            "criado_em": lead.criado_em,
            "atualizado_em": lead.atualizado_em,
        }
        for lead in leads
    ]
    return {"data": data_leads, "error": None}


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    observacao: Optional[str] = None


@router.patch("/leads/{lead_id}")
def atualizar_lead(
    lead_id: uuid.UUID,
    body: LeadUpdate,
    vendedor_id: str = Depends(get_vendedor_atual),
    db: Session = Depends(get_db),
):
    v = _get_vendedor(db, vendedor_id)
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.vendedor_id == v.id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead não encontrado")

    if body.status is not None:
        lead.status = body.status
    if body.observacao is not None:
        lead.observacao = body.observacao
    lead.atualizado_em = datetime.now(timezone.utc)
    db.commit()
    db.refresh(lead)
    return {"id": str(lead.id), "status": lead.status, "observacao": lead.observacao}
