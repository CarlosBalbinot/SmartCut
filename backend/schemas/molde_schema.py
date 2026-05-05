import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

TipoCorte = Literal["simples", "par", "par_sem_espelho"]


# ── Molde individual ────────────────────────────────────────────────


class MoldeOut(BaseModel):
    id: uuid.UUID
    nome: str
    arquivo_path: str | None
    formato: str | None
    peca: str | None
    tamanho: str | None
    sentido_fio: str | None
    tipo_corte: str
    rotacao_base: int = 0
    area_cm2: float | None
    geometria_json: dict[str, Any] | None
    grupo_id: uuid.UUID | None
    criado_em: datetime

    model_config = {"from_attributes": True}


class MoldeUpdate(BaseModel):
    nome: str | None = Field(None, max_length=100)
    peca: str | None = Field(None, max_length=100)
    tamanho: str | None = Field(None, max_length=10)
    sentido_fio: str | None = Field(None, max_length=20)
    tipo_corte: TipoCorte | None = None
    rotacao_base: int | None = None


# ── Preview (arquivo → polylines) ────────────────────────────────────


class PecaPreviewOut(BaseModel):
    """Polyline extraída do arquivo, ainda não salva no banco."""

    nome_sugerido: str
    geometria_json: dict[str, Any]
    area_cm2: float


class PreviewOut(BaseModel):
    arquivo_path: str
    formato: str
    pecas: list[PecaPreviewOut]


# ── Importação em grupo ───────────────────────────────────────────────


class PecaTamanhoCreate(BaseModel):
    """Uma polyline para um tamanho específico dentro de uma parte."""

    tamanho: str = Field(..., max_length=10)
    geometria_json: dict[str, Any]
    area_cm2: float


class ParteCreate(BaseModel):
    """Uma 'parte' do molde (Frente, Costa...) com todos os tamanhos."""

    nome: str = Field(..., max_length=100)
    tipo_corte: TipoCorte = "par"
    sentido_fio: str = Field("vertical", max_length=20)
    rotacao_base: int = 0
    pecas: list[PecaTamanhoCreate]


class GrupoImportCreate(BaseModel):
    """Body do endpoint POST /grupos-molde/importar."""

    nome_grupo: str = Field(..., max_length=150)
    arquivo_path: str
    formato: str
    partes: list[ParteCreate]


# ── Grupos ────────────────────────────────────────────────────────────


class GrupoMoldeCreate(BaseModel):
    nome: str = Field(..., max_length=150)


class GrupoMoldeUpdate(BaseModel):
    nome: str | None = Field(None, max_length=150)
    codigo: str | None = Field(None, max_length=20)


class GrupoMoldeOut(BaseModel):
    id: uuid.UUID
    nome: str
    codigo: str | None = None
    criado_em: datetime
    moldes: list[MoldeOut] = []

    model_config = {"from_attributes": True}


# ── Bulk simples (importação sem grupo) ──────────────────────────────


class PecaBulkCreate(BaseModel):
    nome: str = Field(..., max_length=100)
    peca: str | None = Field(None, max_length=100)
    tamanho: str | None = Field(None, max_length=10)
    sentido_fio: str | None = Field(None, max_length=20)
    tipo_corte: TipoCorte = "simples"
    rotacao_base: int = 0
    geometria_json: dict[str, Any]
    area_cm2: float


class BulkImportCreate(BaseModel):
    arquivo_path: str
    formato: str
    pecas: list[PecaBulkCreate]
