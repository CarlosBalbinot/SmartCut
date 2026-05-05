import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class PedidoVenda(Base):
    __tablename__ = "pedidos_venda"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="venda")
    data_emissao: Mapped[date] = mapped_column(Date, nullable=False)
    prazo_entrega_dias: Mapped[int | None] = mapped_column(Integer, default=20)
    condicoes: Mapped[str | None] = mapped_column(String(20))
    vendedor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendedores.id"), nullable=True
    )
    tabela_preco_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tabelas_preco.id"), nullable=True
    )
    cliente_razao_social: Mapped[str | None] = mapped_column(String(200))
    cliente_cnpj: Mapped[str | None] = mapped_column(String(20))
    cliente_ie: Mapped[str | None] = mapped_column(String(30))
    cliente_endereco: Mapped[str | None] = mapped_column(Text)
    cliente_cidade: Mapped[str | None] = mapped_column(String(100))
    cliente_cep: Mapped[str | None] = mapped_column(String(10))
    cliente_telefone: Mapped[str | None] = mapped_column(String(20))
    cliente_email: Mapped[str | None] = mapped_column(String(100))
    representante: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="rascunho")
    total_pedido: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    comissao_valor: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    observacoes: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    itens: Mapped[list["ItemPedido"]] = relationship(back_populates="pedido", cascade="all, delete-orphan")
    encaixes: Mapped[list["Encaixe"]] = relationship(back_populates="pedido")  # noqa: F821
    vendedor: Mapped["Vendedor | None"] = relationship(back_populates="pedidos")  # noqa: F821
    tabela_preco: Mapped["TabelaPreco | None"] = relationship()  # noqa: F821


class ItemPedido(Base):
    __tablename__ = "itens_pedido"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pedidos_venda.id"), nullable=False
    )
    grupo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grupos_molde.id"), nullable=False
    )
    cor: Mapped[str | None] = mapped_column(String(50))
    lote_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lotes_tecido.id"), nullable=True
    )
    qtd_p: Mapped[int] = mapped_column(Integer, default=0)
    qtd_m: Mapped[int] = mapped_column(Integer, default=0)
    qtd_g: Mapped[int] = mapped_column(Integer, default=0)
    qtd_gg: Mapped[int] = mapped_column(Integer, default=0)
    qtd_g1: Mapped[int] = mapped_column(Integer, default=0)
    qtd_g2: Mapped[int] = mapped_column(Integer, default=0)
    qtd_g3: Mapped[int] = mapped_column(Integer, default=0)
    preco_unitario: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    preco_total: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    pedido: Mapped["PedidoVenda"] = relationship(back_populates="itens")
    grupo: Mapped["GrupoMolde"] = relationship()  # noqa: F821
    lote: Mapped["LoteTecido | None"] = relationship()  # noqa: F821
