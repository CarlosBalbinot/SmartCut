import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric,
    String, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base
from models.tabela_grade import TabelaGrade


class GrupoProduto(Base):
    __tablename__ = "grupos_produto"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    prefixo: Mapped[str] = mapped_column(String(4), nullable=False)
    situacao: Mapped[str] = mapped_column(String(10), nullable=False, default="ativo")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    produtos: Mapped[list["Produto"]] = relationship(back_populates="grupo")


class LinhaGrade(Base):
    __tablename__ = "linhas_grade"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    situacao: Mapped[str] = mapped_column(String(10), nullable=False, default="ativo")


class ColunaGrade(Base):
    __tablename__ = "colunas_grade"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    situacao: Mapped[str] = mapped_column(String(10), nullable=False, default="ativo")


class Produto(Base):
    __tablename__ = "produtos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grupo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("grupos_produto.id"), nullable=False
    )
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    descricao: Mapped[str] = mapped_column(String(300), nullable=False)
    tipo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    almoxarifado: Mapped[str] = mapped_column(String(10), nullable=False, default="01")
    unidade: Mapped[str] = mapped_column(String(10), nullable=False)
    segunda_unidade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tipo_conversao: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fator_conversao: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    classe: Mapped[str | None] = mapped_column(String(50), nullable=True)
    marca: Mapped[str | None] = mapped_column(String(50), nullable=True)
    comissao_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    custo: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    margem_lucro_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    preco_venda: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    ultimo_preco_compra: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tipo_cod_barras: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cod_barras: Mapped[str | None] = mapped_column(String(50), nullable=True)
    peso_gramas: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    peso_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    linha_grade_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tabelas_grade.id", ondelete="SET NULL"), nullable=True
    )
    coluna_grade_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tabelas_grade.id", ondelete="SET NULL"), nullable=True
    )
    data_cadastro: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="ativo")
    tamanhos_disponiveis: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=None)

    # ── Impostos / Faturamento ──────────────────────────────────────
    ncm: Mapped[str | None] = mapped_column(String(8), nullable=True)
    cest: Mapped[str | None] = mapped_column(String(10), nullable=True)
    origem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    icms_incidencia: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    aliquota_ipi_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    codigo_iss: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cod_trib_iss: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cod_cnae: Mapped[str | None] = mapped_column(String(20), nullable=True)
    base_icms_st_ret: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    valor_icms_st_ret: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    base_fcp_st_ret: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    aliq_fcp_st_ret_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    valor_fcp_st_ret: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    nat_receita: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # TES (Tipo de Entrada/Saída) — a tabela "tes" já existe (Fase 2), mas
    # este campo fica sem ForeignKey explícito por ora, a pedido: mantém
    # o Alembic simples enquanto o vínculo produto↔TES (Fase 3) não está
    # finalizado. Era UUID (placeholder anterior); convertido para Integer
    # para bater com o PK real de TES (Integer, autoincrement).
    tes_entrada_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tes_saida_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    codigo_anp: Mapped[str | None] = mapped_column(String(20), nullable=True)
    conta_contabil: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cod_fci: Mapped[str | None] = mapped_column(String(50), nullable=True)
    valor_importacao: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    inf_adicionais: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    inventario_sped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fcp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    um_faturamento: Mapped[str] = mapped_column(String(20), nullable=False, default="primeira_um")

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    grupo: Mapped["GrupoProduto"] = relationship(back_populates="produtos")
    linha_grade: Mapped["TabelaGrade | None"] = relationship(foreign_keys=[linha_grade_id])
    coluna_grade: Mapped["TabelaGrade | None"] = relationship(foreign_keys=[coluna_grade_id])
    skus: Mapped[list["ProdutoSKU"]] = relationship(  # noqa: F821
        back_populates="produto_pai", cascade="all, delete-orphan"
    )

    @property
    def linha_grade_nome(self) -> str | None:
        return self.linha_grade.descricao if self.linha_grade else None

    @property
    def coluna_grade_nome(self) -> str | None:
        return self.coluna_grade.descricao if self.coluna_grade else None

    @property
    def is_pai(self) -> bool:
        return len(self.skus) > 0
