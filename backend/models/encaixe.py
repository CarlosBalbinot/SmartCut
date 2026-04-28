import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Encaixe(Base):
    __tablename__ = "encaixes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pedidos.id"), nullable=False)

    # Nova FK — lote consumido neste encaixe
    lote_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lotes_tecido.id", ondelete="SET NULL"), nullable=True
    )
    # FK legada
    tecido_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tecidos.id", ondelete="SET NULL"), nullable=True
    )

    mapa_json: Mapped[dict | None] = mapped_column(JSONB)
    comp_metros: Mapped[float | None] = mapped_column(Numeric(8, 3))
    peso_kg: Mapped[float | None] = mapped_column(Numeric(8, 3))
    custo_total: Mapped[float | None] = mapped_column(Numeric(12, 2))
    desperdicio_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    num_camadas: Mapped[int] = mapped_column(Integer, default=1)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    data_corte: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="ativo")

    pedido: Mapped["Pedido"] = relationship(back_populates="encaixes")  # noqa: F821
    lote: Mapped["LoteTecido | None"] = relationship(back_populates="encaixes")  # noqa: F821
    defeitos: Mapped[list["Defeito"]] = relationship(back_populates="encaixe")


class Defeito(Base):
    __tablename__ = "defeitos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    encaixe_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("encaixes.id"), nullable=False)
    x_cm: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    y_cm: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    raio_cm: Mapped[float | None] = mapped_column(Numeric(6, 3))
    tipo: Mapped[str | None] = mapped_column(String(30))

    encaixe: Mapped["Encaixe"] = relationship(back_populates="defeitos")
