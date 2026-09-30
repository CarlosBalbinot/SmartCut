import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────
#  Modelo de Tecido
# ─────────────────────────────────────────────────────────────────────


class ModeloCreate(BaseModel):
    nome: str = Field(..., max_length=100)
    tipo: str | None = Field(None, max_length=50)
    max_camadas: int = Field(15, ge=1, le=500)
    tem_direcao: bool = False


class ModeloUpdate(BaseModel):
    nome: str | None = Field(None, max_length=100)
    tipo: str | None = Field(None, max_length=50)
    max_camadas: int | None = Field(None, ge=1, le=500)
    tem_direcao: bool | None = None


class ModeloOut(BaseModel):
    id: uuid.UUID
    nome: str
    tipo: str | None
    max_camadas: int
    tem_direcao: bool = False
    criado_em: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────
#  Cor de Tecido
# ─────────────────────────────────────────────────────────────────────


class CorCreate(BaseModel):
    nome_cor: str = Field(..., max_length=50)
    largura_util_cm: float = Field(..., gt=0)
    gramatura_g_m2: float = Field(..., gt=0)
    encolhimento_pct: float = Field(0, ge=0, le=100)


class CorUpdate(BaseModel):
    nome_cor: str | None = Field(None, max_length=50)
    largura_util_cm: float | None = Field(None, gt=0)
    gramatura_g_m2: float | None = Field(None, gt=0)
    encolhimento_pct: float | None = Field(None, ge=0, le=100)


class CorOut(BaseModel):
    id: uuid.UUID
    modelo_id: uuid.UUID
    nome_cor: str
    largura_util_cm: float
    gramatura_g_m2: float
    encolhimento_pct: float
    criado_em: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────
#  Lote de Tecido
# ─────────────────────────────────────────────────────────────────────


class LoteCreate(BaseModel):
    codigo_lote: str = Field(..., max_length=50)
    peso_inicial_kg: float = Field(..., gt=0)
    valor_kg: float = Field(..., gt=0)
    data_compra: date


class LoteUpdate(BaseModel):
    codigo_lote: str | None = Field(None, max_length=50)
    peso_disponivel_kg: float | None = Field(None, ge=0)
    valor_kg: float | None = Field(None, gt=0)
    data_compra: date | None = None
    status: str | None = Field(None, max_length=20)


class LoteOut(BaseModel):
    id: uuid.UUID
    cor_id: uuid.UUID
    codigo_lote: str
    peso_inicial_kg: float
    peso_disponivel_kg: float
    valor_kg: float
    data_compra: date
    status: str
    criado_em: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────
#  Consumo de Lote
# ─────────────────────────────────────────────────────────────────────


class ConsumoCreate(BaseModel):
    encaixe_id: uuid.UUID | None = None
    pedido_id: uuid.UUID | None = None
    peso_planejado_kg: float | None = Field(None, gt=0)
    peso_retalho_kg: float | None = Field(None, ge=0)
    observacao: str | None = None


class ConsumoOut(BaseModel):
    id: uuid.UUID
    lote_id: uuid.UUID
    encaixe_id: uuid.UUID | None
    pedido_id: uuid.UUID | None
    peso_planejado_kg: float | None
    peso_retalho_kg: float | None
    data_consumo: datetime
    observacao: str | None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────
#  Schemas de saída compostos (hierarquia completa)
# ─────────────────────────────────────────────────────────────────────


class LoteComCorOut(LoteOut):
    """Lote com dados da cor e do modelo (para uso no pedido)."""

    cor_nome: str
    modelo_nome: str
    largura_util_cm: float
    gramatura_g_m2: float
    encolhimento_pct: float


class CorComLotesOut(CorOut):
    lotes: list[LoteOut] = []


class ModeloComCoresOut(ModeloOut):
    cores: list[CorComLotesOut] = []
