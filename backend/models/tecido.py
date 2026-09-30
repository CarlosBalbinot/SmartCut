import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, Uuid, func, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# ─────────────────────────────────────────────────────────────────────
#  Hierarquia: Modelo → Cor → Lote
# ─────────────────────────────────────────────────────────────────────


class ModeloTecido(Base):
    __tablename__ = "modelos_tecido"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo: Mapped[str | None] = mapped_column(String(50))
    max_camadas: Mapped[int] = mapped_column(Integer, default=15)
    # Estampa ou pelo: o tecido não pode ser virado — o enfesto é sempre de
    # face única (nesting_v2/decisor.py descarta o face a face).
    tem_direcao: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cores: Mapped[list["CorTecido"]] = relationship(back_populates="modelo", cascade="all, delete-orphan")


class CorTecido(Base):
    __tablename__ = "cores_tecido"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    modelo_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("modelos_tecido.id"), nullable=False)
    nome_cor: Mapped[str] = mapped_column(String(50), nullable=False)
    largura_util_cm: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    gramatura_g_m2: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    encolhimento_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    modelo: Mapped["ModeloTecido"] = relationship(back_populates="cores")
    lotes: Mapped[list["LoteTecido"]] = relationship(back_populates="cor", cascade="all, delete-orphan")


class LoteTecido(Base):
    __tablename__ = "lotes_tecido"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("cores_tecido.id"), nullable=False)
    codigo_lote: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    peso_inicial_kg: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    peso_disponivel_kg: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    valor_kg: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    data_compra: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="intacto")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cor: Mapped["CorTecido"] = relationship(back_populates="lotes")
    consumos: Mapped[list["ConsumoLote"]] = relationship(back_populates="lote", cascade="all, delete-orphan")
    encaixes: Mapped[list["Encaixe"]] = relationship(back_populates="lote")  # noqa: F821


class ConsumoLote(Base):
    """Movimentação de peso de um lote. CONSUMO baixa o estoque na conclusão
    da OC; ESTORNO devolve o peso (reabertura). `peso_consumido_kg` é a
    quantidade que mexeu no estoque — é o que o estorno devolve, então
    guarda o valor real e não o planejado."""

    __tablename__ = "consumos_lote"
    __table_args__ = (Index("ix_consumos_lote_ordem_corte", "ordem_corte_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lote_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("lotes_tecido.id"), nullable=False)
    # Ordem de Corte que gerou a movimentação (null p/ movimentos antigos,
    # que vinham só do pedido/encaixe).
    ordem_corte_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ordens_corte.id", ondelete="SET NULL"), nullable=True
    )
    encaixe_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("encaixes.id", ondelete="SET NULL"), nullable=True
    )
    pedido_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedidos_venda.id", ondelete="SET NULL"), nullable=True
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="CONSUMO")
    # CONSUMO que este ESTORNO desfaz (null em CONSUMO). Sem isso, concluir
    # e reabrir em ciclo não dá para saber qual baixa foi devolvida: cada
    # reabertura precisa inverter exatamente a última conclusão.
    estorno_de_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("consumos_lote.id", ondelete="SET NULL"), nullable=True
    )
    # kg que saiu (CONSUMO) ou que voltou (ESTORNO) do estoque.
    peso_consumido_kg: Mapped[float | None] = mapped_column(Numeric(10, 3))
    # Planejado pela OC no momento da conclusão (referência do conferência).
    peso_planejado_kg: Mapped[float | None] = mapped_column(Numeric(10, 3))
    peso_retalho_kg: Mapped[float | None] = mapped_column(Numeric(10, 3))
    data_consumo: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    observacao: Mapped[str | None] = mapped_column(Text)

    lote: Mapped["LoteTecido"] = relationship(back_populates="consumos")
