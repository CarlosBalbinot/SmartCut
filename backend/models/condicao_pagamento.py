from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

TIPO_VALIDOS = ("intervalo", "fixo")
SITUACAO_VALIDAS = ("Ativa", "Inativa")


class CondicaoPagamento(Base):
    __tablename__ = "condicoes_pagamento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    descricao: Mapped[str] = mapped_column(String(100), nullable=False)
    # "intervalo" (dias corridos a partir da emissão) ou "fixo" (dia fixo
    # do mês) — ver services/condicao_service.py para o parser de `condicao`.
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    condicao: Mapped[str] = mapped_column(String(70), nullable=False)
    acrescimo: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    desconto: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    situacao: Mapped[str] = mapped_column(String(10), nullable=False, default="Ativa")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
