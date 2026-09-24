import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendedor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("vendedores.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ultimo_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Catalogo(Base):
    __tablename__ = "catalogos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    tabela_preco_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tabelas_preco.id", ondelete="SET NULL"), nullable=True
    )
    arquivo_path: Mapped[str] = mapped_column(String(500), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    acessos: Mapped[List["CatalogoVendedor"]] = relationship(back_populates="catalogo", cascade="all, delete-orphan")


class CatalogoVendedor(Base):
    __tablename__ = "catalogo_vendedor"
    __table_args__ = (UniqueConstraint("catalogo_id", "vendedor_id", name="uq_catalogo_vendedor"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    catalogo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("catalogos.id", ondelete="CASCADE"), nullable=False
    )
    vendedor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("vendedores.id", ondelete="CASCADE"), nullable=False
    )

    catalogo: Mapped["Catalogo"] = relationship(back_populates="acessos")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendedor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("vendedores.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    segmento: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    endereco: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cidade: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    telefone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="novo", server_default="novo")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MetaVendedor(Base):
    __tablename__ = "metas_vendedor"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendedor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("vendedores.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    meta_ativacao: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=10000)
    bonus_logistica: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=300)
    meta_novos_clientes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    bonus_expansao: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=500)
    pedido_minimo: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=1500)
