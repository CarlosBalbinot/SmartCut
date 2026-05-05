import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models.pedido import ItemPedido, PedidoVenda
from models.venda import Empresa, PrecoReferencia, TabelaPreco


def get_ou_criar_empresa(db: Session) -> Empresa:
    empresa = db.execute(select(Empresa)).scalars().first()
    if empresa is None:
        empresa = Empresa()
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
    return empresa


def proximo_numero(db: Session, tipo: str) -> str:
    result = db.execute(
        select(func.max(PedidoVenda.numero)).where(PedidoVenda.tipo == tipo)
    ).scalar()
    if result is None:
        candidate = "000001"
    else:
        try:
            candidate = str(int(result) + 1).zfill(6)
        except (ValueError, TypeError):
            count = db.execute(
                select(func.count(PedidoVenda.id)).where(PedidoVenda.tipo == tipo)
            ).scalar() or 0
            candidate = str(count + 1).zfill(6)

    # Garantir unicidade global (evitar colisão entre tipos)
    while db.execute(
        select(PedidoVenda.id).where(PedidoVenda.numero == candidate)
    ).scalar() is not None:
        candidate = str(int(candidate) + 1).zfill(6)

    return candidate


def get_preco(
    grupo_id: uuid.UUID,
    tabela_id: uuid.UUID,
    condicoes: str,
    db: Session,
) -> Optional[Decimal]:
    preco_ref = db.execute(
        select(PrecoReferencia).where(
            PrecoReferencia.grupo_id == grupo_id,
            PrecoReferencia.tabela_id == tabela_id,
        )
    ).scalars().first()
    if not preco_ref:
        return None
    if condicoes == "avista":
        return Decimal(str(preco_ref.preco_avista))
    return Decimal(str(preco_ref.preco_aprazo))


def calcular_totais(
    itens: list,
    tabela: TabelaPreco,
    condicoes: str,
    db: Session,
) -> tuple:
    total = sum(Decimal(str(item.preco_total or 0)) for item in itens)
    comissao = total * Decimal(str(tabela.comissao_pct or 0))
    return total, comissao


def recalcular_pedido(db: Session, pedido_id: uuid.UUID) -> None:
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido or not pedido.tabela_preco_id:
        return
    itens = db.execute(
        select(ItemPedido).where(ItemPedido.pedido_id == pedido_id)
    ).scalars().all()
    tabela = db.get(TabelaPreco, pedido.tabela_preco_id)
    if not tabela:
        return
    total, comissao = calcular_totais(itens, tabela, pedido.condicoes or "", db)
    pedido.total_pedido = total
    pedido.comissao_valor = comissao
