from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ConfiguracaoEmpresaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    aliquota_simples: Decimal
    custo_etiqueta: Decimal


class ConfiguracaoEmpresaUpdate(BaseModel):
    aliquota_simples: Optional[Decimal] = None
    custo_etiqueta: Optional[Decimal] = None


class ConfiguracaoCustosFixosOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    metros_rolo_overlock: int
    custo_rolo_overlock: Decimal
    metros_rolo_reta: int
    custo_rolo_reta: Decimal
    custo_saquinho_lote: Decimal
    unidades_saquinho_lote: int
    custo_caixa: Decimal
    pecas_por_caixa: int
    distancia_costureira_km: Decimal
    num_viagens: int
    consumo_veiculo_km_l: Decimal
    preco_combustivel: Decimal


class ConfiguracaoCustosFixosUpdate(BaseModel):
    metros_rolo_overlock: Optional[int] = None
    custo_rolo_overlock: Optional[Decimal] = None
    metros_rolo_reta: Optional[int] = None
    custo_rolo_reta: Optional[Decimal] = None
    custo_saquinho_lote: Optional[Decimal] = None
    unidades_saquinho_lote: Optional[int] = None
    custo_caixa: Optional[Decimal] = None
    pecas_por_caixa: Optional[int] = None
    distancia_costureira_km: Optional[Decimal] = None
    num_viagens: Optional[int] = None
    consumo_veiculo_km_l: Optional[Decimal] = None
    preco_combustivel: Optional[Decimal] = None


class PrecificacaoCreate(BaseModel):
    grupo_id: UUID
    tamanho: str
    faixa_tamanho: str = "padrao"
    valor_kg_tecido: Optional[Decimal] = None
    pecas_por_kg: Optional[Decimal] = None
    custo_tecido_manual: Optional[Decimal] = None
    custo_tecido_encaixe: Optional[Decimal] = None
    usar_custo_encaixe: bool = False
    custo_costura: Decimal = Decimal("0")
    metros_linha_overlock: Decimal = Decimal("0")
    metros_linha_reta: Decimal = Decimal("0")
    pecas_por_viagem: int = 50
    margem_desejada: Decimal = Decimal("0.60")
    preco_venda_final: Optional[Decimal] = None


class PrecificacaoUpdate(BaseModel):
    faixa_tamanho: Optional[str] = None
    valor_kg_tecido: Optional[Decimal] = None
    pecas_por_kg: Optional[Decimal] = None
    custo_tecido_manual: Optional[Decimal] = None
    custo_tecido_encaixe: Optional[Decimal] = None
    usar_custo_encaixe: Optional[bool] = None
    custo_costura: Optional[Decimal] = None
    metros_linha_overlock: Optional[Decimal] = None
    metros_linha_reta: Optional[Decimal] = None
    pecas_por_viagem: Optional[int] = None
    margem_desejada: Optional[Decimal] = None
    preco_venda_final: Optional[Decimal] = None


class PrecificacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    grupo_id: UUID
    tamanho: str
    faixa_tamanho: str
    valor_kg_tecido: Optional[Decimal]
    pecas_por_kg: Optional[Decimal]
    custo_tecido_manual: Optional[Decimal]
    custo_tecido_encaixe: Optional[Decimal]
    usar_custo_encaixe: bool
    custo_costura: Decimal
    metros_linha_overlock: Decimal
    metros_linha_reta: Decimal
    pecas_por_viagem: int
    margem_desejada: Decimal
    preco_venda_sugerido: Optional[Decimal]
    preco_venda_final: Optional[Decimal]
    ativo: bool
