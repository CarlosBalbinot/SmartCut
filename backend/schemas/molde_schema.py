import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

TipoCorte = Literal["simples", "par", "par_sem_espelho"]


# ── Molde individual ────────────────────────────────────────────────


class MoldeUpdate(BaseModel):
    nome: str | None = Field(None, max_length=100)
    peca: str | None = Field(None, max_length=100)
    tamanho: str | None = Field(None, max_length=10)
    sentido_fio: str | None = Field(None, max_length=20)
    tipo_corte: TipoCorte | None = None
    rotacao_base: int | None = None


class SimetriaIn(BaseModel):
    """Peças de uma parte (todos os tamanhos) para o aviso de simetria."""

    geometrias: list[dict[str, Any] | None]
    sentido_fio: str | None = Field(None, max_length=20)
    rotacao_base: int = 0


# ── Importação em grupo ───────────────────────────────────────────────


class PecaTamanhoCreate(BaseModel):
    """Uma polyline para um tamanho específico dentro de uma parte."""

    tamanho: str = Field(..., max_length=10)
    geometria_json: dict[str, Any]
    area_cm2: float


class ParteCreate(BaseModel):
    """Uma 'parte' do molde (Frente, Costa...) com todos os tamanhos."""

    nome: str = Field(..., max_length=100)
    # SEM default, de propósito: o tipo de corte decide quantas peças saem de
    # um molde (1 ou 2) e se a segunda sai espelhada. Chutar aqui dobrava a
    # produção de peça sem ninguém pedir — o default antigo era "par".
    tipo_corte: TipoCorte
    sentido_fio: str = Field("vertical", max_length=20)
    rotacao_base: int = 0
    pecas: list[PecaTamanhoCreate]


class GrupoImportCreate(BaseModel):
    """Body do endpoint POST /grupos-molde/importar."""

    nome_grupo: str = Field(..., max_length=150)
    arquivo_path: str
    formato: str
    produto_id: uuid.UUID | None = None
    partes: list[ParteCreate]


# ── Grupos ────────────────────────────────────────────────────────────


class GrupoMoldeUpdate(BaseModel):
    nome: str | None = Field(None, max_length=150)
    codigo: str | None = Field(None, max_length=20)


# ── Bulk simples (importação sem grupo) ──────────────────────────────


class PecaBulkCreate(BaseModel):
    nome: str = Field(..., max_length=100)
    peca: str | None = Field(None, max_length=100)
    tamanho: str | None = Field(None, max_length=10)
    sentido_fio: str | None = Field(None, max_length=20)
    tipo_corte: TipoCorte
    rotacao_base: int = 0
    geometria_json: dict[str, Any]
    area_cm2: float


class BulkImportCreate(BaseModel):
    arquivo_path: str
    formato: str
    pecas: list[PecaBulkCreate]
