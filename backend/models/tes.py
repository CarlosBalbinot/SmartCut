from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

TIPOS_VALIDOS = ("Entrada", "Saída")
SITUACOES_VALIDAS = ("Ativo", "Inativo")


class TES(Base):
    """Tipo de Entrada e Saída — classifica operações fiscais.

    Cada produto terá um TES Entrada e um TES Saída padrão (vínculo feito
    na Fase 3); por ora, apenas o cadastro.
    """

    __tablename__ = "tes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    descricao: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    natureza_operacao: Mapped[str] = mapped_column(String(200), nullable=False)
    cfop: Mapped[str] = mapped_column(String(10), nullable=False)
    csosn: Mapped[str] = mapped_column(String(3), nullable=False)
    # CST do ICMS — usado no lugar do CSOSN para Lucro Presumido/Real
    # ("00","10","20","30","40","41","50","51","60","70","90").
    cst_icms: Mapped[str | None] = mapped_column(String(2), nullable=True)
    origem: Mapped[str] = mapped_column(String(1), nullable=False)
    modalidade_bc_icms: Mapped[str] = mapped_column(String(1), nullable=False)
    reducao_bc_icms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    aliquota_icms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    valor_icms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    pis_cst: Mapped[str] = mapped_column(String(2), nullable=False)
    pis_aliquota: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cofins_cst: Mapped[str] = mapped_column(String(2), nullable=False)
    cofins_aliquota: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gera_financeiro: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    movimenta_estoque: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    situacao: Mapped[str] = mapped_column(String(10), nullable=False, default="Ativo")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
