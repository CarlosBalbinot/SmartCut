import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ConfiguracaoEmpresa(Base):
    __tablename__ = "configuracao_empresa"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aliquota_simples: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=Decimal("7.3000"))
    custo_etiqueta: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    # Produção (M2a): motor dos encaixes ("v2" spyrrow + OR-Tools; "v1" o
    # antigo, que também é a reserva quando o v2 falha), a maior mesa de
    # corte da fábrica e a economia mínima para sugerir usá-la.
    motor_encaixe: Mapped[str] = mapped_column(String(5), nullable=False, default="v2", server_default="v2")
    comprimento_max_mesa_cm: Mapped[int] = mapped_column(Integer, nullable=False, default=200, server_default="200")
    alerta_economia_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("5.00"), server_default="5.00"
    )


class ConfiguracaoCustosFixos(Base):
    __tablename__ = "configuracao_custos_fixos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metros_rolo_overlock: Mapped[int] = mapped_column(Integer, nullable=False, default=5000)
    custo_rolo_overlock: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    metros_rolo_reta: Mapped[int] = mapped_column(Integer, nullable=False, default=5000)
    custo_rolo_reta: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    custo_saquinho_lote: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("148.00"))
    unidades_saquinho_lote: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    custo_caixa: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    pecas_por_caixa: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    distancia_costureira_km: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("1.5"))
    num_viagens: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    consumo_veiculo_km_l: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("12.0"))
    preco_combustivel: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("0.00"))


class Precificacao(Base):
    __tablename__ = "precificacoes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grupo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("grupos_molde.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tamanho: Mapped[str] = mapped_column(String(10), nullable=False)
    faixa_tamanho: Mapped[str] = mapped_column(String(20), nullable=False, default="padrao")

    # Custo tecido — kg-based OU manual/encaixe
    valor_kg_tecido: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    pecas_por_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    custo_tecido_manual: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    custo_tecido_encaixe: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    usar_custo_encaixe: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Custo costura e linha
    custo_costura: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    metros_linha_overlock: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0"))
    metros_linha_reta: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0"))

    # Logística
    pecas_por_viagem: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    # Precificação
    margem_desejada: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0.6000"))
    preco_venda_sugerido: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    preco_venda_final: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
