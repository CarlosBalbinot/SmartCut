import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Situacao = Literal["ativo", "inativo"]
IcmsIncidencia = Literal["normal", "st", "isento", "outros"]
UmFaturamento = Literal["primeira_um", "segunda_um"]

# Campos de texto livre convertidos para maiúsculo antes de salvar — segunda
# garantia além do uppercase já aplicado no onChange do frontend. Aplicado só
# em ProdutoCreate/ProdutoUpdate (não em ProdutoBase, para não afetar ProdutoOut).
_CAMPOS_UPPER = ("descricao", "marca", "classe")


# ── Grupo de Produto ───────────────────────────────────────────────────

class GrupoProdutoCreate(BaseModel):
    nome: str = Field(..., max_length=150)
    prefixo: str = Field(..., min_length=1, max_length=4)
    situacao: Situacao = "ativo"


class GrupoProdutoUpdate(BaseModel):
    nome: str | None = Field(None, max_length=150)
    prefixo: str | None = Field(None, min_length=1, max_length=4)
    situacao: Situacao | None = None


class GrupoProdutoOut(BaseModel):
    id: uuid.UUID
    codigo: str
    nome: str
    prefixo: str
    situacao: Situacao
    criado_em: datetime

    model_config = {"from_attributes": True}


# ── Linha / Coluna de Grade ─────────────────────────────────────────────

class GradeItemCreate(BaseModel):
    nome: str = Field(..., max_length=100)
    situacao: Situacao = "ativo"


class GradeItemOut(BaseModel):
    id: uuid.UUID
    nome: str
    situacao: Situacao

    model_config = {"from_attributes": True}


# ── Produto ───────────────────────────────────────────────────────────

class ProdutoBase(BaseModel):
    grupo_id: uuid.UUID
    descricao: str = Field(..., max_length=300)
    tipo: str | None = Field(None, max_length=50)
    almoxarifado: str = Field("01", max_length=10)
    unidade: str = Field(..., max_length=10)
    segunda_unidade: str | None = Field(None, max_length=10)
    tipo_conversao: str | None = Field(None, max_length=30)
    fator_conversao: Decimal | None = None
    classe: str | None = Field(None, max_length=50)
    marca: str | None = Field(None, max_length=50)
    comissao_pct: Decimal = Decimal("0")
    custo: Decimal = Decimal("0")
    margem_lucro_pct: Decimal = Decimal("0")
    preco_venda: Decimal = Decimal("0")
    ultimo_preco_compra: Decimal = Decimal("0")
    tipo_cod_barras: str | None = Field(None, max_length=20)
    cod_barras: str | None = Field(None, max_length=50)
    peso_gramas: Decimal | None = None
    peso_kg: Decimal | None = None
    linha_grade_id: int | None = None
    coluna_grade_id: int | None = None
    status: Situacao = "ativo"
    tamanhos_disponiveis: list[str] | None = None

    # Impostos / Faturamento
    ncm: str | None = Field(None, min_length=8, max_length=8)
    cest: str | None = Field(None, max_length=10)
    origem: int = Field(0, ge=0, le=8)
    icms_incidencia: IcmsIncidencia = "normal"
    aliquota_ipi_pct: Decimal = Decimal("0")
    codigo_iss: str | None = Field(None, max_length=20)
    cod_trib_iss: str | None = Field(None, max_length=20)
    cod_cnae: str | None = Field(None, max_length=20)
    base_icms_st_ret: Decimal = Decimal("0")
    valor_icms_st_ret: Decimal = Decimal("0")
    base_fcp_st_ret: Decimal = Decimal("0")
    aliq_fcp_st_ret_pct: Decimal = Decimal("0")
    valor_fcp_st_ret: Decimal = Decimal("0")
    nat_receita: str | None = Field(None, max_length=50)
    codigo_anp: str | None = Field(None, max_length=20)
    conta_contabil: str | None = Field(None, max_length=50)
    cod_fci: str | None = Field(None, max_length=50)
    valor_importacao: Decimal = Decimal("0")
    inf_adicionais: str | None = Field(None, max_length=1000)
    inventario_sped: bool = True
    fcp: bool = False
    um_faturamento: UmFaturamento = "primeira_um"


class ProdutoCreate(ProdutoBase):
    @field_validator(*_CAMPOS_UPPER, mode="before")
    @classmethod
    def to_upper(cls, v):
        return v.upper() if isinstance(v, str) else v


class ProdutoUpdate(BaseModel):
    grupo_id: uuid.UUID | None = None
    descricao: str | None = Field(None, max_length=300)
    tipo: str | None = Field(None, max_length=50)
    almoxarifado: str | None = Field(None, max_length=10)
    unidade: str | None = Field(None, max_length=10)
    segunda_unidade: str | None = Field(None, max_length=10)
    tipo_conversao: str | None = Field(None, max_length=30)
    fator_conversao: Decimal | None = None
    classe: str | None = Field(None, max_length=50)
    marca: str | None = Field(None, max_length=50)
    comissao_pct: Decimal | None = None
    custo: Decimal | None = None
    margem_lucro_pct: Decimal | None = None
    preco_venda: Decimal | None = None
    ultimo_preco_compra: Decimal | None = None
    tipo_cod_barras: str | None = Field(None, max_length=20)
    cod_barras: str | None = Field(None, max_length=50)
    peso_gramas: Decimal | None = None
    peso_kg: Decimal | None = None
    linha_grade_id: int | None = None
    coluna_grade_id: int | None = None
    status: Situacao | None = None
    tamanhos_disponiveis: list[str] | None = None

    ncm: str | None = Field(None, min_length=8, max_length=8)
    cest: str | None = Field(None, max_length=10)
    origem: int | None = Field(None, ge=0, le=8)
    icms_incidencia: IcmsIncidencia | None = None
    aliquota_ipi_pct: Decimal | None = None
    codigo_iss: str | None = Field(None, max_length=20)
    cod_trib_iss: str | None = Field(None, max_length=20)
    cod_cnae: str | None = Field(None, max_length=20)
    base_icms_st_ret: Decimal | None = None
    valor_icms_st_ret: Decimal | None = None
    base_fcp_st_ret: Decimal | None = None
    aliq_fcp_st_ret_pct: Decimal | None = None
    valor_fcp_st_ret: Decimal | None = None
    nat_receita: str | None = Field(None, max_length=50)
    codigo_anp: str | None = Field(None, max_length=20)
    conta_contabil: str | None = Field(None, max_length=50)
    cod_fci: str | None = Field(None, max_length=50)
    valor_importacao: Decimal | None = None
    inf_adicionais: str | None = Field(None, max_length=1000)
    inventario_sped: bool | None = None
    fcp: bool | None = None
    um_faturamento: UmFaturamento | None = None

    @field_validator(*_CAMPOS_UPPER, mode="before")
    @classmethod
    def to_upper(cls, v):
        return v.upper() if isinstance(v, str) else v


class ProdutoOut(ProdutoBase):
    id: uuid.UUID
    codigo: str
    data_cadastro: date
    criado_em: datetime
    grupo: GrupoProdutoOut | None = None
    linha_grade_nome: str | None = None
    coluna_grade_nome: str | None = None
    is_pai: bool = False

    model_config = {"from_attributes": True}


# ── SKU (produto filho / combinação de grade) ────────────────────────────

class ComboItem(BaseModel):
    linha_item_id: int | None = None
    coluna_item_id: int | None = None


class SkuGerarRequest(BaseModel):
    combinacoes: list[ComboItem]


class SkuUpdate(BaseModel):
    codigo: str | None = Field(None, max_length=50)
    preco_venda: Decimal | None = None
    situacao: str | None = None


class ProdutoSkuOut(BaseModel):
    id: int
    produto_pai_id: uuid.UUID
    linha_item_id: int | None = None
    coluna_item_id: int | None = None
    linha_item_descricao: str | None = None
    coluna_item_descricao: str | None = None
    codigo: str
    preco_venda: Decimal | None = None
    preco_manual: bool
    situacao: str
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PropagarPrecoResponse(BaseModel):
    atualizados: int
    ignorados: int
    mensagem: str


class SkuSincronizarRequest(BaseModel):
    combinacoes: list[ComboItem] = []
    remover_sku_ids: list[int] = []


class SkuSincronizarResponse(BaseModel):
    criados: int
    removidos: int
    bloqueados: list[str]


# ── Listagem "vendável" (excluir_pais=true) ──────────────────────────────
# Mistura produtos autônomos e SKUs filhos numa única forma de exibição —
# ver produto_service.listar_sellable. `id` de um SKU é "sku-<int>" (string)
# pois ProdutoSKU.id não é UUID; use produto_pai_id/sku_id para ações.

class ProdutoListagemOut(BaseModel):
    id: str
    codigo: str
    descricao: str
    descricao_completa: str
    grupo_id: uuid.UUID
    unidade: str
    preco_venda: Decimal
    status: str
    is_sku: bool = False
    sku_id: int | None = None
    produto_pai_id: uuid.UUID | None = None
    codigo_pai: str | None = None
    linha_desc: str | None = None
    coluna_desc: str | None = None


# ── Busca para adicionar item ao pedido de venda ─────────────────────────
# Mistura produtos "pai" (com grade de SKUs) e "avulsos" (sem SKUs) — ver
# produto_service.busca_pedido. Usado pelo Passo 1 do modal de adicionar
# item em PedidoVendaDetalhePage.

class ProdutoBuscaPedidoOut(BaseModel):
    tipo: Literal["pai", "avulso"]
    id: str
    codigo: str
    descricao: str
    grupo: str | None = None
    preco_venda: Decimal
    unidade: str | None = None
    descricao_completa: str | None = None
    linha_grade_id: int | None = None
    coluna_grade_id: int | None = None
    linha_grade_nome: str | None = None
    coluna_grade_nome: str | None = None


# ── Grade de um produto pai, para o Passo 2 do modal de adicionar item ────

class GradeEixoItemOut(BaseModel):
    id: int
    codigo_curto: str
    descricao: str
    ordem: int


class GradeEixoOut(BaseModel):
    id: int | None = None
    descricao: str | None = None
    itens: list[GradeEixoItemOut] = []


class GradeProdutoResumoOut(BaseModel):
    id: uuid.UUID
    codigo: str
    descricao: str
    grupo: str | None = None


class GradeSkuOut(BaseModel):
    id: int
    codigo: str
    linha_item_id: int | None = None
    coluna_item_id: int | None = None
    preco_venda: Decimal | None = None
    preco_origem: Literal["sku", "pai", "sem_preco"]
    situacao: str


class GradePedidoOut(BaseModel):
    produto: GradeProdutoResumoOut
    linha_grade: GradeEixoOut
    coluna_grade: GradeEixoOut
    skus: list[GradeSkuOut]
