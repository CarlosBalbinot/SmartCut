import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ConfiguracaoEmpresa(Base):
    __tablename__ = "configuracao_empresa"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    aliquota_simples: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, default=Decimal("7.3000")
    )
    custo_etiqueta: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )


class ConfiguracaoCustosFixos(Base):
    __tablename__ = "configuracao_custos_fixos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    metros_rolo_overlock: Mapped[int] = mapped_column(Integer, nullable=False, default=5000)
    custo_rolo_overlock: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    metros_rolo_reta: Mapped[int] = mapped_column(Integer, nullable=False, default=5000)
    custo_rolo_reta: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    custo_saquinho_lote: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("148.00"))
    unidades_saquinho_lote: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    custo_caixa: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    pecas_por_caixa: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    distancia_costureira_km: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("1.5")
    )
    num_viagens: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    consumo_veiculo_km_l: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("12.0")
    )
    preco_combustivel: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("0.00"))


class Precificacao(Base):
    __tablename__ = "precificacoes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    grupo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
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
    custo_costura: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    metros_linha_overlock: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("0")
    )
    metros_linha_reta: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("0")
    )

    # Logística
    pecas_por_viagem: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    # Precificação
    margem_desejada: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.6000")
    )
    preco_venda_sugerido: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    preco_venda_final: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
