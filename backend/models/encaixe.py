import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Encaixe(Base):
    __tablename__ = "encaixes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedidos_venda.id", ondelete="SET NULL"), nullable=True
    )

    # Nova FK — lote consumido neste encaixe
    lote_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lotes_tecido.id", ondelete="SET NULL"), nullable=True
    )
    # FK legada
    tecido_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tecidos.id", ondelete="SET NULL"), nullable=True
    )

    mapa_json: Mapped[dict | None] = mapped_column(JSON)
    comp_metros: Mapped[float | None] = mapped_column(Numeric(8, 3))
    peso_kg: Mapped[float | None] = mapped_column(Numeric(8, 3))
    custo_total: Mapped[float | None] = mapped_column(Numeric(12, 2))
    desperdicio_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    num_camadas: Mapped[int] = mapped_column(Integer, default=1)
    # Numeração sequencial própria do encaixe (ENC-001, ENC-002...),
    # independente do número do PedidoVenda — gerada em
    # nesting_service._salvar_encaixe via COUNT(*)+1.
    numero: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Identificação textual — herda o "Nome / identificação" que o usuário
    # digitou no Encaixe Rápido (PedidoVenda.observacoes_internas).
    descricao: Mapped[str | None] = mapped_column(String(200), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    data_corte: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="ativo")

    pedido: Mapped["PedidoVenda | None"] = relationship(back_populates="encaixes")  # noqa: F821
    lote: Mapped["LoteTecido | None"] = relationship(back_populates="encaixes")  # noqa: F821
    defeitos: Mapped[list["Defeito"]] = relationship(back_populates="encaixe")


class Defeito(Base):
    __tablename__ = "defeitos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    encaixe_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("encaixes.id"), nullable=False)
    x_cm: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    y_cm: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    raio_cm: Mapped[float | None] = mapped_column(Numeric(6, 3))
    tipo: Mapped[str | None] = mapped_column(String(30))

    encaixe: Mapped["Encaixe"] = relationship(back_populates="defeitos")
