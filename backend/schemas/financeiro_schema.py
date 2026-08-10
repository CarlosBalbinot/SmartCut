from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ── ContaBancaria ─────────────────────────────────────────────────────────────

class ContaBancariaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nome: str
    tipo: str
    ativo: bool


class ContaBancariaCreate(BaseModel):
    nome: str
    tipo: str


class ContaBancariaUpdate(BaseModel):
    nome: Optional[str] = None
    tipo: Optional[str] = None
    ativo: Optional[bool] = None


# ── CategoriaFinanceira ───────────────────────────────────────────────────────

class CategoriaFinanceiraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nome: str
    tipo: str
    cor: str


class CategoriaFinanceiraCreate(BaseModel):
    nome: str
    tipo: str
    cor: str


class CategoriaFinanceiraUpdate(BaseModel):
    nome: Optional[str] = None
    tipo: Optional[str] = None
    cor: Optional[str] = None


# ── AnexoLancamento ───────────────────────────────────────────────────────────

class AnexoLancamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    lancamento_id: UUID
    arquivo_path: str
    tipo: str
    nome_original: str
    created_at: datetime


# ── Lancamento ────────────────────────────────────────────────────────────────

class LancamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tipo: str
    descricao: str
    valor: Decimal
    valor_original: Optional[Decimal] = None
    data_vencimento: date
    data_pagamento: Optional[date]
    status: str
    parcela_numero: Optional[int]
    parcela_total: Optional[int]
    conta_bancaria_id: Optional[UUID]
    categoria_id: Optional[UUID]
    compra_id: Optional[UUID]
    venda_id: Optional[UUID]
    recorrente: bool
    recorrencia_origem_id: Optional[UUID]
    created_at: datetime
    anexos: List[AnexoLancamentoOut] = []


class LancamentoCreate(BaseModel):
    tipo: str
    descricao: str
    valor: Decimal
    data_vencimento: date
    conta_bancaria_id: Optional[UUID] = None
    categoria_id: Optional[UUID] = None
    compra_id: Optional[UUID] = None
    venda_id: Optional[UUID] = None
    recorrente: bool = False
    parcela_numero: Optional[int] = None
    parcela_total: Optional[int] = None


class LancamentoUpdate(BaseModel):
    tipo: Optional[str] = None
    descricao: Optional[str] = None
    valor: Optional[Decimal] = None
    data_vencimento: Optional[date] = None
    data_pagamento: Optional[date] = None
    status: Optional[str] = None
    conta_bancaria_id: Optional[UUID] = None
    categoria_id: Optional[UUID] = None
    recorrente: Optional[bool] = None


class ConfirmarPagamento(BaseModel):
    conta_bancaria_id: UUID
    data_pagamento: date


# ── CompraFinanceira ──────────────────────────────────────────────────────────

class CompraFinanceiraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    fornecedor: str
    descricao: Optional[str]
    valor_total: Decimal
    data_compra: date
    nf_pdf_path: Optional[str]
    created_at: datetime
    total_parcelas: int = 0
    parcelas_pagas: int = 0


class CompraCreate(BaseModel):
    fornecedor: str
    descricao: Optional[str] = None
    valor_total: Decimal
    data_compra: date
    parcelas: int = 1
    primeiro_vencimento: date
    categoria_id: Optional[UUID] = None


class CompraComLancamentosOut(CompraFinanceiraOut):
    lancamentos: List[LancamentoOut] = []


class CompraUpdate(BaseModel):
    fornecedor: Optional[str] = None
    descricao: Optional[str] = None
    valor_total: Optional[Decimal] = None
    data_compra: Optional[date] = None


# ── VendaFinanceira ───────────────────────────────────────────────────────────

class VendaFinanceiraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    cliente: str
    descricao: Optional[str]
    valor_total: Decimal
    data_venda: date
    nf_pdf_path: Optional[str]
    created_at: datetime
    total_parcelas: int = 0
    parcelas_pagas: int = 0


class VendaCreate(BaseModel):
    cliente: str
    descricao: Optional[str] = None
    valor_total: Decimal
    data_venda: date
    parcelas: int = 1
    primeiro_vencimento: date
    categoria_id: Optional[UUID] = None


class VendaComLancamentosOut(VendaFinanceiraOut):
    lancamentos: List[LancamentoOut] = []


class VendaUpdate(BaseModel):
    cliente: Optional[str] = None
    descricao: Optional[str] = None
    valor_total: Optional[Decimal] = None
    data_venda: Optional[date] = None


# ── Importação de NF-e XML ────────────────────────────────────────────────────

class ParcelaImportadaOut(BaseModel):
    numero: str
    vencimento: Optional[date] = None
    valor: Decimal


class NFeImportadaOut(BaseModel):
    fornecedor: str
    cnpj_fornecedor: Optional[str] = None
    valor_total: Decimal
    data_emissao: date
    numero_nf: Optional[str] = None
    parcelas: List[ParcelaImportadaOut] = []


class ImportacaoXMLResultOut(BaseModel):
    sucesso: bool
    dados: Optional[NFeImportadaOut] = None
    erro: Optional[str] = None


class ParcelaImportarIn(BaseModel):
    vencimento: date
    valor: Decimal


class CompraImportarXMLCreate(BaseModel):
    fornecedor: str
    descricao: Optional[str] = None
    valor_total: Decimal
    data_compra: date
    categoria_id: Optional[UUID] = None
    parcelas: List[ParcelaImportarIn]


class VendaImportarXMLCreate(BaseModel):
    cliente: str
    descricao: Optional[str] = None
    valor_total: Decimal
    data_venda: date
    categoria_id: Optional[UUID] = None
    parcelas: List[ParcelaImportarIn]


# ── Saldo por Conta ───────────────────────────────────────────────────────────

class SaldoContaOut(BaseModel):
    conta_id: UUID
    conta_nome: str
    saldo_inicial: Decimal
    total_entradas: Decimal
    total_saidas: Decimal
    saldo_atual: Decimal


# ── Projeção ──────────────────────────────────────────────────────────────────

class ProjecaoMesOut(BaseModel):
    mes: int
    ano: int
    saldo_inicial: Decimal
    total_previsto_entrar: Decimal
    total_previsto_sair: Decimal
    saldo_final_projetado: Decimal
    lancamentos_count: int


# ── MetaMensal ────────────────────────────────────────────────────────────────

class MetaMensalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    mes: int
    ano: int
    valor_meta: Decimal
    tipo: str
    descricao: Optional[str]


class MetaMensalCreate(BaseModel):
    mes: int
    ano: int
    valor_meta: Decimal
    tipo: str
    descricao: Optional[str] = None


class MetaMensalUpdate(BaseModel):
    valor_meta: Optional[Decimal] = None
    descricao: Optional[str] = None
