import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Numeric,
    String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Empresa(Base):
    __tablename__ = "empresa"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    razao_social: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    cnpj: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ie: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    endereco: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cidade: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cep: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    telefone1: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    telefone2: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    site: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    logo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TabelaPreco(Base):
    __tablename__ = "tabelas_preco"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(50), nullable=False)
    comissao_pct: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    precos_referencia: Mapped[List["PrecoReferencia"]] = relationship(
        back_populates="tabela", cascade="all, delete-orphan"
    )


class PrecoReferencia(Base):
    __tablename__ = "precos_referencia"
    __table_args__ = (
        UniqueConstraint("grupo_id", "tabela_id", name="uq_preco_ref_grupo_tabela"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grupo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("grupos_molde.id", ondelete="CASCADE"), nullable=False
    )
    tabela_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tabelas_preco.id", ondelete="CASCADE"), nullable=False
    )
    preco_avista: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    preco_aprazo: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tabela: Mapped["TabelaPreco"] = relationship(back_populates="precos_referencia")


class Vendedor(Base):
    __tablename__ = "vendedores"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    telefone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pedidos: Mapped[List["PedidoVenda"]] = relationship(back_populates="vendedor")  # noqa: F821
