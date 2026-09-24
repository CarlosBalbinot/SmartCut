import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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


class Empresa(Base):
    __tablename__ = "empresa"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    razao_social: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    cnpj: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ie: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    endereco: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    endereco_numero: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    endereco_bairro: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    codigo_ibge_municipio: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    codigo_pais: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="1058")
    cidade: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cep: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    telefone1: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    telefone2: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    site: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    logo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Fiscal
    regime_tributario: Mapped[str] = mapped_column(String(30), nullable=False, default="Simples Nacional")
    uf_emitente: Mapped[str] = mapped_column(String(2), nullable=False, default="RS")
    ambiente_sefaz: Mapped[str] = mapped_column(String(20), nullable=False, default="Homologacao")
    certificado_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    certificado_senha: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    nfe_serie_padrao: Mapped[str] = mapped_column(String(10), nullable=False, default="001")
    nfe_numero_atual: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    nfce_serie_padrao: Mapped[str] = mapped_column(String(10), nullable=False, default="002")
    nfce_numero_atual: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TabelaPreco(Base):
    __tablename__ = "tabelas_preco"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(50), nullable=False)
    # Legado (fração, 0.10 = 10%) — sem uso: a comissão agora vem de
    # VendedorTabelaComissao / Vendedor.comissao_padrao_pct.
    comissao_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    precos_referencia: Mapped[List["PrecoReferencia"]] = relationship(
        back_populates="tabela", cascade="all, delete-orphan"
    )
    precos_produto: Mapped[List["PrecoTabelaProduto"]] = relationship(
        back_populates="tabela", cascade="all, delete-orphan"
    )


class PrecoReferencia(Base):
    __tablename__ = "precos_referencia"
    __table_args__ = (UniqueConstraint("grupo_id", "tabela_id", name="uq_preco_ref_grupo_tabela"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grupo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("grupos_molde.id", ondelete="CASCADE"), nullable=False
    )
    tabela_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tabelas_preco.id", ondelete="CASCADE"), nullable=False
    )
    preco_avista: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    preco_aprazo: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tem_plus_size: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    preco_avista_plus: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    preco_aprazo_plus: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tabela: Mapped["TabelaPreco"] = relationship(back_populates="precos_referencia")


class PrecoTabelaProduto(Base):
    """Preço de um produto pai ou de um SKU específico numa tabela de preço.

    Convive com PrecoReferencia (preço legado por GrupoMolde). Na resolução
    (services/venda_service.resolver_preco_item) o preço do SKU vence o do
    produto pai, que vence o do grupo.
    """

    __tablename__ = "precos_tabela_produto"
    __table_args__ = (
        CheckConstraint(
            "(produto_id IS NOT NULL AND sku_id IS NULL) OR (produto_id IS NULL AND sku_id IS NOT NULL)",
            name="ck_preco_tab_prod_produto_xor_sku",
        ),
        UniqueConstraint("tabela_preco_id", "produto_id", name="uq_preco_tab_prod_produto"),
        UniqueConstraint("tabela_preco_id", "sku_id", name="uq_preco_tab_prod_sku"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tabela_preco_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tabelas_preco.id", ondelete="CASCADE"), nullable=False
    )
    produto_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("produtos.id", ondelete="CASCADE"), nullable=True
    )
    sku_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("produtos_sku.id", ondelete="CASCADE"), nullable=True
    )
    preco_avista: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    preco_aprazo: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tem_plus_size: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    preco_avista_plus: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    preco_aprazo_plus: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tabela: Mapped["TabelaPreco"] = relationship(back_populates="precos_produto")
    produto: Mapped[Optional["Produto"]] = relationship()  # noqa: F821
    sku: Mapped[Optional["ProdutoSKU"]] = relationship()  # noqa: F821


class Vendedor(Base):
    __tablename__ = "vendedores"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)
    tipo_pessoa: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    nome_fantasia: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    endereco: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    numero: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    complemento: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bairro: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    municipio: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    estado: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    cep: Mapped[Optional[str]] = mapped_column(String(9), nullable=True)
    telefone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    celular: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    fax: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    cpf_cnpj: Mapped[Optional[str]] = mapped_column(String(18), nullable=True)
    rg_ie: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    inscricao_municipal: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    descricao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comissao_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    # Percentual (0–100) usado quando não há VendedorTabelaComissao para a
    # tabela do pedido.
    comissao_padrao_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    dia_pagto: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pct_pago_emissao: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=100)
    pct_pago_baixa: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email_nfe: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    data_cadastro: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="ativo")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pedidos: Mapped[List["PedidoVenda"]] = relationship(back_populates="vendedor")  # noqa: F821
    comissoes_tabela: Mapped[List["VendedorTabelaComissao"]] = relationship(
        back_populates="vendedor", cascade="all, delete-orphan"
    )


class VendedorTabelaComissao(Base):
    """Comissão (%) de um vendedor numa tabela de preço específica."""

    __tablename__ = "vendedor_tabela_comissao"
    __table_args__ = (
        UniqueConstraint("vendedor_id", "tabela_preco_id", name="uq_vendedor_tabela_comissao"),
        CheckConstraint(
            "comissao_pct >= 0 AND comissao_pct <= 100",
            name="ck_vendedor_tabela_comissao_pct",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendedor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("vendedores.id", ondelete="CASCADE"), nullable=False
    )
    tabela_preco_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tabelas_preco.id", ondelete="CASCADE"), nullable=False
    )
    comissao_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vendedor: Mapped["Vendedor"] = relationship(back_populates="comissoes_tabela")
    tabela: Mapped["TabelaPreco"] = relationship()
