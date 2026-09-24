import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class ContaBancaria(Base):
    __tablename__ = "contas_bancarias"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    lancamentos: Mapped[list["Lancamento"]] = relationship(back_populates="conta_bancaria")
    saldos_iniciais: Mapped[list["SaldoInicialConta"]] = relationship(back_populates="conta_bancaria")


class CategoriaFinanceira(Base):
    __tablename__ = "categorias_financeiras"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    cor: Mapped[str] = mapped_column(String(7), nullable=False)

    lancamentos: Mapped[list["Lancamento"]] = relationship(back_populates="categoria")


class CompraFinanceira(Base):
    __tablename__ = "compras_financeiras"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fornecedor: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    data_compra: Mapped[date] = mapped_column(Date, nullable=False)
    numero_nf: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nf_pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lancamentos: Mapped[list["Lancamento"]] = relationship(back_populates="compra")


class VendaFinanceira(Base):
    __tablename__ = "vendas_financeiras"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    data_venda: Mapped[date] = mapped_column(Date, nullable=False)
    numero_nf: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nf_pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lancamentos: Mapped[list["Lancamento"]] = relationship(back_populates="venda")


class Lancamento(Base):
    __tablename__ = "lancamentos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    descricao: Mapped[str] = mapped_column(String(500), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    valor_original: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    data_vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    data_pagamento: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDENTE")
    parcela_numero: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parcela_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    conta_bancaria_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contas_bancarias.id"), nullable=True
    )
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("categorias_financeiras.id"), nullable=True
    )
    compra_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("compras_financeiras.id"), nullable=True
    )
    venda_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("vendas_financeiras.id"), nullable=True
    )
    recorrente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recorrencia_origem_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lancamentos.id"), nullable=True
    )
    transferencia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conta_bancaria: Mapped["ContaBancaria | None"] = relationship(back_populates="lancamentos")
    categoria: Mapped["CategoriaFinanceira | None"] = relationship(back_populates="lancamentos")
    compra: Mapped["CompraFinanceira | None"] = relationship(back_populates="lancamentos")
    venda: Mapped["VendaFinanceira | None"] = relationship(back_populates="lancamentos")
    recorrencias: Mapped[list["Lancamento"]] = relationship(
        back_populates="recorrencia_origem",
        foreign_keys="[Lancamento.recorrencia_origem_id]",
    )
    recorrencia_origem: Mapped["Lancamento | None"] = relationship(
        back_populates="recorrencias",
        foreign_keys="[Lancamento.recorrencia_origem_id]",
        remote_side="Lancamento.id",
    )
    anexos: Mapped[list["AnexoLancamento"]] = relationship(back_populates="lancamento", cascade="all, delete-orphan")


class AnexoLancamento(Base):
    __tablename__ = "anexos_lancamento"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lancamento_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("lancamentos.id"), nullable=False)
    arquivo_path: Mapped[str] = mapped_column(String(500), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    nome_original: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lancamento: Mapped["Lancamento"] = relationship(back_populates="anexos")


class SaldoInicialConta(Base):
    __tablename__ = "saldo_inicial_conta"
    __table_args__ = (UniqueConstraint("conta_bancaria_id", "mes", "ano", name="uq_saldo_inicial_conta_mes_ano"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conta_bancaria_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contas_bancarias.id"), nullable=False
    )
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    conta_bancaria: Mapped["ContaBancaria"] = relationship(back_populates="saldos_iniciais")


class MetaMensal(Base):
    __tablename__ = "metas_mensais"
    __table_args__ = (UniqueConstraint("mes", "ano", "tipo", name="uq_meta_mensal_mes_ano_tipo"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_meta: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(500), nullable=True)
