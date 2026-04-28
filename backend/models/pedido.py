import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Pedido(Base):
    __tablename__ = "pedidos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    num_pedido: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    data_pedido: Mapped[date] = mapped_column(Date, nullable=False)
    cliente: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(30), default="rascunho")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pedido_tecidos: Mapped[list["PedidoTecido"]] = relationship(back_populates="pedido", cascade="all, delete-orphan")
    pecas: Mapped[list["PedidoPeca"]] = relationship(back_populates="pedido")
    encaixes: Mapped[list["Encaixe"]] = relationship(back_populates="pedido")  # noqa: F821


class PedidoTecido(Base):
    __tablename__ = "pedido_tecidos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pedidos.id"), nullable=False)

    # Nova FK — hierarquia Modelo → Cor → Lote
    lote_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lotes_tecido.id", ondelete="SET NULL"), nullable=True
    )
    # FK legada (dados antigos)
    tecido_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tecidos.id", ondelete="SET NULL"), nullable=True
    )

    pedido: Mapped["Pedido"] = relationship(back_populates="pedido_tecidos")
    lote: Mapped["LoteTecido | None"] = relationship(back_populates="pedido_tecidos")  # noqa: F821
    tecido: Mapped["Tecido | None"] = relationship(back_populates="pedido_tecidos")  # noqa: F821


class PedidoPeca(Base):
    __tablename__ = "pedido_pecas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pedidos.id"), nullable=False)
    molde_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("moldes.id"), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    cor: Mapped[str | None] = mapped_column(String(50))
    lote: Mapped[str | None] = mapped_column(String(50))

    # Nova FK — cor do tecido (hierarquia nova)
    cor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cores_tecido.id", ondelete="SET NULL"), nullable=True
    )
    # FK legada
    tecido_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tecidos.id", ondelete="SET NULL"), nullable=True
    )

    pedido: Mapped["Pedido"] = relationship(back_populates="pecas")
    molde: Mapped["Molde"] = relationship(back_populates="pedido_pecas")  # noqa: F821
    cor_tecido: Mapped["CorTecido | None"] = relationship(foreign_keys=[cor_id], back_populates="pedido_pecas")  # noqa: F821
    tecido: Mapped["Tecido | None"] = relationship(foreign_keys=[tecido_id])  # noqa: F821
