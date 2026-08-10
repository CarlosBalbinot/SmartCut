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
    cidade: Optional[str] = None
    cep: Optional[str] = None
    telefone1: Optional[str] = None
    telefone2: Optional[str] = None
    email: Optional[str] = None
    site: Optional[str] = None


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
    nome: str
    telefone: Optional[str]
    email: Optional[str]
    ativo: bool
    criado_em: datetime


class VendedorCreate(BaseModel):
    nome: str
    telefone: Optional[str] = None
    email: Optional[str] = None


class VendedorUpdate(BaseModel):
    nome: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    ativo: Optional[bool] = None


# ── ItemPedidoVenda ───────────────────────────────────────────────────────

class ItemPedidoVendaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    pedido_id: UUID
    grupo_id: UUID
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


class ItemPedidoVendaCreate(BaseModel):
    grupo_id: UUID
    cor: Optional[str] = None
    qtd_p: int = 0
    qtd_m: int = 0
    qtd_g: int = 0
    qtd_gg: int = 0
    qtd_g1: int = 0
    qtd_g2: int = 0
    qtd_g3: int = 0
    preco_unitario: Optional[Decimal] = None


# ── PedidoVenda ───────────────────────────────────────────────────────────

class PedidoVendaOut(BaseModel):
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
    cliente_cidade: Optional[str]
    cliente_cep: Optional[str]
    cliente_telefone: Optional[str]
    cliente_email: Optional[str]
    representante: Optional[str]
    status: str
    total_pedido: Decimal
    comissao_valor: Decimal
    criado_em: datetime


class PedidoVendaComItensOut(PedidoVendaOut):
    itens: List[ItemPedidoVendaOut] = []


class PedidoVendaCreate(BaseModel):
    data_emissao: date
    prazo_entrega_dias: int = 20
    condicoes: Optional[str] = None
    vendedor_id: Optional[UUID] = None
    tabela_preco_id: Optional[UUID] = None
    cliente_razao_social: Optional[str] = None
    cliente_cnpj: Optional[str] = None
    cliente_ie: Optional[str] = None
    cliente_endereco: Optional[str] = None
    cliente_cidade: Optional[str] = None
    cliente_cep: Optional[str] = None
    cliente_telefone: Optional[str] = None
    cliente_email: Optional[str] = None
    representante: Optional[str] = None


class PedidoVendaUpdate(BaseModel):
    prazo_entrega_dias: Optional[int] = None
    condicoes: Optional[str] = None
    vendedor_id: Optional[UUID] = None
    tabela_preco_id: Optional[UUID] = None
    cliente_razao_social: Optional[str] = None
    cliente_cnpj: Optional[str] = None
    cliente_ie: Optional[str] = None
    cliente_endereco: Optional[str] = None
    cliente_cidade: Optional[str] = None
    cliente_cep: Optional[str] = None
    cliente_telefone: Optional[str] = None
    cliente_email: Optional[str] = None
    representante: Optional[str] = None
    status: Optional[str] = None
