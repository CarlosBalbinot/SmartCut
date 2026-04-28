import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class DefeitoCreate(BaseModel):
    x_cm: float = Field(..., ge=0)
    y_cm: float = Field(..., ge=0)
    raio_cm: float | None = Field(None, gt=0)
    tipo: str | None = Field(None, max_length=30)


class DefeitoOut(BaseModel):
    id: uuid.UUID
    x_cm: float
    y_cm: float
    raio_cm: float | None
    tipo: str | None

    model_config = {"from_attributes": True}


class EncaixeCreate(BaseModel):
    pedido_id: uuid.UUID
    num_camadas: int = Field(1, ge=1)
    data_corte: date | None = None
    defeitos: list[DefeitoCreate] = Field(default_factory=list)


class EncaixeOut(BaseModel):
    id: uuid.UUID
    pedido_id: uuid.UUID
    tecido_id: uuid.UUID | None
    mapa_json: dict[str, Any] | None
    comp_metros: float | None
    peso_kg: float | None
    custo_total: float | None
    desperdicio_pct: float | None
    num_camadas: int
    status: str
    criado_em: datetime
    data_corte: date | None
    defeitos: list[DefeitoOut] = []

    model_config = {"from_attributes": True}
