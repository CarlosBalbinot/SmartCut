import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Encaixe(Base):
    __tablename__ = "encaixes"
    __table_args__ = (UniqueConstraint("numero", name="uq_encaixes_numero"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Rastreio do pedido de origem; a geração pela OC preenche os dois.
    pedido_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedidos_venda.id", ondelete="SET NULL"), nullable=True
    )
    ordem_corte_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ordens_corte.id", ondelete="SET NULL"), nullable=True
    )

    # Lote consumido neste encaixe (a FK legada tecido_id → tecidos foi
    # removida na migração e1c7a4b90d2f).
    lote_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lotes_tecido.id", ondelete="SET NULL"), nullable=True
    )

    mapa_json: Mapped[dict | None] = mapped_column(JSON)
    comp_metros: Mapped[float | None] = mapped_column(Numeric(8, 3))
    peso_kg: Mapped[float | None] = mapped_column(Numeric(8, 3))
    custo_total: Mapped[float | None] = mapped_column(Numeric(12, 2))
    desperdicio_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    num_camadas: Mapped[int] = mapped_column(Integer, default=1)
    # Numeração sequencial própria do encaixe (ENC-001, ENC-002...),
    # independente do número do PedidoVenda — gerada em
    # nesting_service._numerar via MAX(numero)+1 contando também os
    # deletados (soft-delete), para nunca reaproveitar um número.
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
    # Enfesto multicor (plano de corte por produto): uma linha por cor/lote.
    # Vazio = encaixe de um lote só (lote_id, peso_kg × num_camadas).
    camadas_cor: Mapped[list["EncaixeCamada"]] = relationship(
        back_populates="encaixe", cascade="all, delete-orphan", order_by="EncaixeCamada.ordem"
    )

    def consumo_por_lote(self) -> dict[uuid.UUID, float]:
        """kg planejados por lote neste encaixe (todas as camadas). Multicor:
        soma das linhas de camadas_cor; senão o lote do encaixe."""
        if self.camadas_cor:
            saida: dict[uuid.UUID, float] = {}
            for c in self.camadas_cor:
                if c.lote_id is not None:
                    saida[c.lote_id] = saida.get(c.lote_id, 0.0) + float(c.peso_kg or 0) * c.camadas
            return saida
        if self.lote_id is None or self.peso_kg is None:
            return {}
        return {self.lote_id: float(self.peso_kg) * (self.num_camadas or 1)}


class EncaixeCamada(Base):
    """Camadas de UMA cor (lote) num encaixe multicor.

    peso_kg / custo / comp_metros são de UMA camada DESTE lote: o risco é o
    mesmo para todas as cores, mas gramatura, largura, encolhimento e preço
    são do tecido de cada uma — por isso o consumo de cada lote sai daqui e
    não do Encaixe. O Encaixe guarda a média ponderada (mesmo total)."""

    __tablename__ = "encaixe_camadas"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    encaixe_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("encaixes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lote_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lotes_tecido.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Ordem no enfesto (de baixo para cima) e o nome da cor para a ficha.
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    camadas: Mapped[int] = mapped_column(Integer, nullable=False)
    comp_metros: Mapped[float | None] = mapped_column(Numeric(8, 3))
    peso_kg: Mapped[float | None] = mapped_column(Numeric(8, 3))
    custo: Mapped[float | None] = mapped_column(Numeric(12, 2))

    encaixe: Mapped["Encaixe"] = relationship(back_populates="camadas_cor")
    lote: Mapped["LoteTecido | None"] = relationship()  # noqa: F821


class Defeito(Base):
    __tablename__ = "defeitos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    encaixe_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("encaixes.id"), nullable=False)
    x_cm: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    y_cm: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    raio_cm: Mapped[float | None] = mapped_column(Numeric(6, 3))
    tipo: Mapped[str | None] = mapped_column(String(30))

    encaixe: Mapped["Encaixe"] = relationship(back_populates="defeitos")
