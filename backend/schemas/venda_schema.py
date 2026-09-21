from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field


# ── Empresa ───────────────────────────────────────────────────────────────

class EmpresaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    razao_social: Optional[str]
    cnpj: Optional[str]
    ie: Optional[str]
    endereco: Optional[str]
    endereco_numero: Optional[str]
    endereco_bairro: Optional[str]
    codigo_ibge_municipio: Optional[str]
    codigo_pais: Optional[str]
    cidade: Optional[str]
    cep: Optional[str]
    telefone1: Optional[str]
    telefone2: Optional[str]
    email: Optional[str]
    site: Optional[str]
    logo_path: Optional[str]
    criado_em: datetime

    @computed_field
    @property
    def logo_url(self) -> Optional[str]:
        if not self.logo_path:
            return None
        # Normaliza separadores e extrai a parte relativa a partir de "uploads/"
        path = self.logo_path.replace("\\", "/")
        if "uploads/" in path:
            rel = path.split("uploads/")[-1]
            return f"/uploads/{rel}"
        return None


class EmpresaUpdate(BaseModel):
    razao_social: Optional[str] = None
    cnpj: Optional[str] = None
    ie: Optional[str] = None
    endereco: Optional[str] = None
    endereco_numero: Optional[str] = None
    endereco_bairro: Optional[str] = None
    codigo_ibge_municipio: Optional[str] = None
    codigo_pais: Optional[str] = None
    cidade: Optional[str] = None
    cep: Optional[str] = None
    telefone1: Optional[str] = None
    telefone2: Optional[str] = None
    email: Optional[str] = None
    site: Optional[str] = None


class EmpresaFiscalOut(BaseModel):
    regime_tributario: str
    uf_emitente: str
    ambiente_sefaz: str
    certificado_path: Optional[str]
    certificado_senha: Optional[str]
    certificado_valido: bool
    nfe_serie_padrao: str
    nfe_numero_atual: int
    nfce_serie_padrao: str
    nfce_numero_atual: int


class EmpresaFiscalUpdate(BaseModel):
    regime_tributario: Optional[str] = None
    uf_emitente: Optional[str] = None
    ambiente_sefaz: Optional[str] = None
    certificado_path: Optional[str] = None
    certificado_senha: Optional[str] = None
    nfe_serie_padrao: Optional[str] = None
    nfe_numero_atual: Optional[int] = None
    nfce_serie_padrao: Optional[str] = None
    nfce_numero_atual: Optional[int] = None


class TestarCertificadoIn(BaseModel):
    certificado_path: str
    certificado_senha: str


# ── TabelaPreco ───────────────────────────────────────────────────────────

class TabelaPrecoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nome: str
    comissao_pct: Decimal
    ativa: bool
    criado_em: datetime


class TabelaPrecoCreate(BaseModel):
    nome: str
    comissao_pct: Decimal


class TabelaPrecoUpdate(BaseModel):
    nome: Optional[str] = None
    comissao_pct: Optional[Decimal] = None
    ativa: Optional[bool] = None


class TabelaPrecoItemOut(BaseModel):
    grupo_id: UUID
    codigo: Optional[str]
    nome: str
    preco_avista: Decimal
    preco_aprazo: Decimal
    tem_plus_size: bool = False
    preco_avista_plus: Optional[Decimal] = None
    preco_aprazo_plus: Optional[Decimal] = None


class TabelaPrecoItemCreate(BaseModel):
    grupo_id: UUID
    preco_avista: Decimal
    preco_aprazo: Decimal
    tem_plus_size: Optional[bool] = False
    preco_avista_plus: Optional[Decimal] = None
    preco_aprazo_plus: Optional[Decimal] = None


# ── PrecoReferencia ───────────────────────────────────────────────────────

class PrecoReferenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    grupo_id: UUID
    tabela_id: UUID
    preco_avista: Decimal
    preco_aprazo: Decimal
    tem_plus_size: bool = False
    preco_avista_plus: Optional[Decimal] = None
    preco_aprazo_plus: Optional[Decimal] = None
    criado_em: datetime


class PrecoReferenciaCreate(BaseModel):
    tabela_id: UUID
    preco_avista: Decimal
    preco_aprazo: Decimal
    tem_plus_size: Optional[bool] = False
    preco_avista_plus: Optional[Decimal] = None
    preco_aprazo_plus: Optional[Decimal] = None


class PrecoReferenciaUpdate(BaseModel):
    preco_avista: Optional[Decimal] = None
    preco_aprazo: Optional[Decimal] = None
    tem_plus_size: Optional[bool] = None
    preco_avista_plus: Optional[Decimal] = None
    preco_aprazo_plus: Optional[Decimal] = None


# ── Vendedor ──────────────────────────────────────────────────────────────

class VendedorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    codigo: Optional[str] = None
    tipo_pessoa: Optional[str] = None
    nome: str
    nome_fantasia: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    telefone: Optional[str]
    celular: Optional[str] = None
    fax: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    rg_ie: Optional[str] = None
    inscricao_municipal: Optional[str] = None
    descricao: Optional[str] = None
    comissao_pct: Decimal
    dia_pagto: int
    pct_pago_emissao: Decimal
    pct_pago_baixa: Decimal
    email: Optional[str]
    email_nfe: Optional[str] = None
    data_cadastro: date
    status: str
    ativo: bool
    criado_em: datetime


class VendedorCreate(BaseModel):
    tipo_pessoa: Optional[str] = None
    nome: str
    nome_fantasia: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    telefone: Optional[str] = None
    celular: Optional[str] = None
    fax: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    rg_ie: Optional[str] = None
    inscricao_municipal: Optional[str] = None
    descricao: Optional[str] = None
    comissao_pct: Decimal = Decimal("0")
    dia_pagto: int = 0
    pct_pago_emissao: Decimal = Decimal("100")
    pct_pago_baixa: Decimal = Decimal("0")
    email: Optional[str] = None
    email_nfe: Optional[str] = None
    status: str = "ativo"


class VendedorUpdate(BaseModel):
    tipo_pessoa: Optional[str] = None
    nome: Optional[str] = None
    nome_fantasia: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    telefone: Optional[str] = None
    celular: Optional[str] = None
    fax: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    rg_ie: Optional[str] = None
    inscricao_municipal: Optional[str] = None
    descricao: Optional[str] = None
    comissao_pct: Optional[Decimal] = None
    dia_pagto: Optional[int] = None
    pct_pago_emissao: Optional[Decimal] = None
    pct_pago_baixa: Optional[Decimal] = None
    email: Optional[str] = None
    email_nfe: Optional[str] = None
    status: Optional[str] = None
    ativo: Optional[bool] = None


# ── ItemPedidoVenda ───────────────────────────────────────────────────────

class ItemPedidoVendaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    pedido_id: UUID
    grupo_id: UUID
    produto_id: Optional[UUID] = None
    cor: Optional[str]
    qtd_p: int
    qtd_m: int
    qtd_g: int
    qtd_gg: int
    qtd_g1: int
    qtd_g2: int
    qtd_g3: int
    preco_unitario: Optional[Decimal]
    preco_total: Optional[Decimal]
    tes_id: Optional[int] = None
    desconto_pct: Decimal = Decimal("0")
    desconto_valor: Decimal = Decimal("0")
    acrescimo_pct: Decimal = Decimal("0")
    acrescimo_valor: Decimal = Decimal("0")


class ItemPedidoVendaCreate(BaseModel):
    grupo_id: UUID
    produto_id: Optional[UUID] = None
    cor: Optional[str] = None
    qtd_p: int = 0
    qtd_m: int = 0
    qtd_g: int = 0
    qtd_gg: int = 0
    qtd_g1: int = 0
    qtd_g2: int = 0
    qtd_g3: int = 0
    preco_unitario: Optional[Decimal] = None
    tes_id: Optional[int] = None
    desconto_pct: Decimal = Decimal("0")
    desconto_valor: Decimal = Decimal("0")
    acrescimo_pct: Decimal = Decimal("0")
    acrescimo_valor: Decimal = Decimal("0")


# ── PedidoVenda ───────────────────────────────────────────────────────────

# Campos fiscais/financeiros/transporte novos, compartilhados entre Create
# e Update para não duplicar a lista (todos opcionais nos dois — a Create
# aceita omissão e usa os defaults do model; a Update só aplica o que vier).
class _PedidoVendaCamposFiscais(BaseModel):
    tes_id: Optional[int] = None
    desconto_geral_pct: Optional[Decimal] = None
    desconto_geral_valor: Optional[Decimal] = None
    acrescimo_pct: Optional[Decimal] = None
    acrescimo_valor: Optional[Decimal] = None
    valor_frete: Optional[Decimal] = None
    valor_seguro: Optional[Decimal] = None
    valor_despesas: Optional[Decimal] = None
    indicador_presenca: Optional[str] = None
    informacoes_adicionais: Optional[str] = None
    observacoes_internas: Optional[str] = None
    transportadora_id: Optional[int] = None
    tipo_frete: Optional[str] = None
    peso_liquido: Optional[Decimal] = None
    peso_bruto: Optional[Decimal] = None
    qtd_volumes: Optional[int] = None
    especie_volumes: Optional[str] = None
    placa_veiculo: Optional[str] = None
    uf_veiculo: Optional[str] = None


class PedidoVendaOut(_PedidoVendaCamposFiscais):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    numero: str
    data_emissao: date
    prazo_entrega_dias: int
    condicoes: Optional[str]
    vendedor_id: Optional[UUID]
    tabela_preco_id: Optional[UUID]
    cliente_razao_social: Optional[str]
    cliente_cnpj: Optional[str]
    cliente_ie: Optional[str]
    cliente_endereco: Optional[str]
    cliente_numero: Optional[str] = None
    cliente_bairro: Optional[str] = None
    cliente_cidade: Optional[str]
    cliente_uf: Optional[str] = None
    cliente_cep: Optional[str]
    cliente_codigo_ibge_municipio: Optional[str] = None
    cliente_codigo_pais: Optional[str] = None
    cliente_telefone: Optional[str]
    cliente_email: Optional[str]
    representante: Optional[str]
    status: str
    total_pedido: Decimal
    comissao_valor: Decimal
    nfe_id: Optional[int] = None
    criado_em: datetime


class PedidoVendaComItensOut(PedidoVendaOut):
    itens: List[ItemPedidoVendaOut] = []


class PedidoVendaCreate(_PedidoVendaCamposFiscais):
    data_emissao: date
    prazo_entrega_dias: int = 20
    condicoes: Optional[str] = None
    vendedor_id: Optional[UUID] = None
    tabela_preco_id: Optional[UUID] = None
    cliente_razao_social: Optional[str] = None
    cliente_cnpj: Optional[str] = None
    cliente_ie: Optional[str] = None
    cliente_endereco: Optional[str] = None
    cliente_numero: Optional[str] = None
    cliente_bairro: Optional[str] = None
    cliente_cidade: Optional[str] = None
    cliente_uf: Optional[str] = None
    cliente_cep: Optional[str] = None
    cliente_codigo_ibge_municipio: Optional[str] = None
    cliente_codigo_pais: Optional[str] = None
    cliente_telefone: Optional[str] = None
    cliente_email: Optional[str] = None
    representante: Optional[str] = None


class PedidoVendaUpdate(_PedidoVendaCamposFiscais):
    prazo_entrega_dias: Optional[int] = None
    condicoes: Optional[str] = None
    vendedor_id: Optional[UUID] = None
    tabela_preco_id: Optional[UUID] = None
    cliente_razao_social: Optional[str] = None
    cliente_cnpj: Optional[str] = None
    cliente_ie: Optional[str] = None
    cliente_endereco: Optional[str] = None
    cliente_numero: Optional[str] = None
    cliente_bairro: Optional[str] = None
    cliente_cidade: Optional[str] = None
    cliente_uf: Optional[str] = None
    cliente_cep: Optional[str] = None
    cliente_codigo_ibge_municipio: Optional[str] = None
    cliente_codigo_pais: Optional[str] = None
    cliente_telefone: Optional[str] = None
    cliente_email: Optional[str] = None
    representante: Optional[str] = None
    # status não é mais editável por aqui — ver PATCH /{id}/status, que
    # valida as transições (Aberto/Fechado/Cancelado).


class PedidoStatusUpdate(BaseModel):
    status: str
