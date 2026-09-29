"""Ordem de Corte (OC) — produção a partir de um pedido de venda.

Corte sempre por pedido: cada pedido tem no máximo UMA OC não cancelada
(índice único parcial uq_ordens_corte_pedido_ativa). A escolha de
tecido/lote fica na OC (OrdemCorteTecido), nunca no ItemPedido.

Os itens da OC são um snapshot dos itens do pedido no momento da geração;
pedido_hash guarda a assinatura desses itens para detectar quando o pedido
mudou depois (OC "desatualizada").
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

STATUS_OC = ("RASCUNHO", "ENVIADA", "EM_CORTE", "CONCLUIDA", "CANCELADA")
# SEM_SOBRA: camadas por tamanho, sem cortar peça a mais.
# MENOS_ENFESTOS: menos enfestos, aceitando sobra (regra antiga do nesting).
MODOS_CAMADAS = ("SEM_SOBRA", "MENOS_ENFESTOS")
# Comprimento máximo de cada encaixe (cm) — tamanho da mesa de corte.
COMPRIMENTO_MAX_PADRAO_CM = 150
COMPRIMENTO_MAX_MIN_CM = 50
COMPRIMENTO_MAX_MAX_CM = 2000


class OrdemCorte(Base):
    __tablename__ = "ordens_corte"
    __table_args__ = (
        # 1 OC não cancelada por pedido — índice parcial (SQLite ≥ 3.8 e
        # Postgres). O service valida antes para devolver um 409 legível.
        Index(
            "uq_ordens_corte_pedido_ativa",
            "pedido_id",
            unique=True,
            sqlite_where=text("status <> 'CANCELADA'"),
            postgresql_where=text("status <> 'CANCELADA'"),
        ),
        CheckConstraint(
            f"comprimento_max_cm BETWEEN {COMPRIMENTO_MAX_MIN_CM} AND {COMPRIMENTO_MAX_MAX_CM}",
            name="ck_ordens_corte_comprimento_max_cm",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Sequência própria (OC-0001), MAX+1 sobre todas, inclusive canceladas.
    numero: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    pedido_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("pedidos_venda.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RASCUNHO")
    modo_camadas: Mapped[str] = mapped_column(String(20), nullable=False, default="SEM_SOBRA")
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # LIMITE do comprimento de cada encaixe (a mesa onde o tecido é aberto):
    # risco menor sai com o que precisar, maior é dividido em partes.
    comprimento_max_cm: Mapped[int] = mapped_column(
        Integer, nullable=False, default=COMPRIMENTO_MAX_PADRAO_CM, server_default=str(COMPRIMENTO_MAX_PADRAO_CM)
    )
    # sha256 dos itens do pedido (id, produto, SKU, quantidade) na geração.
    pedido_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    # Linha do tempo da produção (OC6a). As três datas são gravadas pelo
    # service nas transições: enviada_em ao enviar, iniciada_em ao iniciar o
    # corte, concluida_em ao concluir. `cortador` é texto livre (nome de quem
    # executou o corte) — sem FK para usuário: o corte é feito por quem
    # estiver na fábrica, nem sempre com login no sistema.
    enviada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    iniciada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cortador: Mapped[str | None] = mapped_column(String(150), nullable=True)

    pedido: Mapped["PedidoVenda"] = relationship()  # noqa: F821
    itens: Mapped[list["ItemOrdemCorte"]] = relationship(
        back_populates="ordem_corte", cascade="all, delete-orphan", order_by="ItemOrdemCorte.numero_item"
    )
    tecidos: Mapped[list["OrdemCorteTecido"]] = relationship(back_populates="ordem_corte", cascade="all, delete-orphan")
    encaixes: Mapped[list["Encaixe"]] = relationship()  # noqa: F821


class ItemOrdemCorte(Base):
    __tablename__ = "itens_ordem_corte"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ordem_corte_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ordens_corte.id", ondelete="CASCADE"), nullable=False
    )
    # Sem FK rígida para o item do pedido: o snapshot sobrevive a itens
    # removidos do pedido (a OC fica "desatualizada" até ser refeita).
    item_pedido_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    numero_item: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("produtos_sku.id"), nullable=True)
    produto_pai_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("produtos.id"), nullable=False)
    # Descrições da grade do SKU: linha = cor, coluna = tamanho.
    cor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tamanho: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    grupo_molde_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("grupos_molde.id", ondelete="SET NULL"), nullable=True
    )

    ordem_corte: Mapped["OrdemCorte"] = relationship(back_populates="itens")
    sku: Mapped["ProdutoSKU | None"] = relationship()  # noqa: F821
    produto_pai: Mapped["Produto"] = relationship()  # noqa: F821
    grupo_molde: Mapped["GrupoMolde | None"] = relationship()  # noqa: F821


class OrdemCorteTecido(Base):
    """Tecido/lote escolhido para cada (produto pai, cor) da OC."""

    __tablename__ = "ordem_corte_tecidos"
    __table_args__ = (
        UniqueConstraint("ordem_corte_id", "produto_pai_id", "cor", name="uq_ordem_corte_tecidos_produto_cor"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ordem_corte_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ordens_corte.id", ondelete="CASCADE"), nullable=False
    )
    produto_pai_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("produtos.id"), nullable=False)
    cor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Nulo até o usuário escolher o lote (pendência SEM_TECIDO).
    lote_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lotes_tecido.id", ondelete="SET NULL"), nullable=True
    )

    ordem_corte: Mapped["OrdemCorte"] = relationship(back_populates="tecidos")
    produto_pai: Mapped["Produto"] = relationship()  # noqa: F821
    lote: Mapped["LoteTecido | None"] = relationship()  # noqa: F821
