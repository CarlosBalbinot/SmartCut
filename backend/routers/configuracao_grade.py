from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from services.grade_service import aplicar_mascara, obter_configuracao

router = APIRouter(prefix="/api/v1/configuracao-grade", tags=["configuracao_grade"])

_MOD_VER = "configuracoes_ver"
_MOD_EDITAR = "configuracoes_editar"


# ── Schemas ─────────────────────────────────────────────────────────────

class ConfiguracaoGradeUpdate(BaseModel):
    mascara: Optional[str] = Field(None, max_length=100)
    separador: Optional[str] = Field(None, max_length=5)
    tamanho_seq: Optional[int] = Field(None, ge=1, le=10)


class ConfiguracaoGradeResponse(BaseModel):
    mascara: str
    separador: str
    tamanho_seq: int

    model_config = {"from_attributes": True}


class PreviewRequest(BaseModel):
    mascara: str = Field(..., max_length=100)
    separador: str = Field("-", max_length=5)
    tamanho_seq: int = Field(4, ge=1, le=10)
    grupo_prefixo: str = "LG"
    seq_exemplo: int = 1
    cor_codigo: Optional[str] = None
    tam_codigo: Optional[str] = None


class PreviewResponse(BaseModel):
    codigo_gerado: str


# ── Rotas ───────────────────────────────────────────────────────────────

@router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD_VER, "ver"))])
def obter(db: Session = Depends(get_db)):
    config = obter_configuracao(db)
    return {"data": ConfiguracaoGradeResponse.model_validate(config), "error": None}


@router.patch("/", response_model=dict, dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))])
def atualizar(payload: ConfiguracaoGradeUpdate, db: Session = Depends(get_db)):
    config = obter_configuracao(db)
    dados = payload.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(config, campo, valor)
    db.commit()
    db.refresh(config)
    return {"data": ConfiguracaoGradeResponse.model_validate(config), "error": None}


@router.post(
    "/preview", response_model=dict,
    dependencies=[Depends(require_permission(_MOD_VER, "ver"))],
)
def preview(payload: PreviewRequest):
    codigo = aplicar_mascara(
        payload.mascara, payload.separador, payload.tamanho_seq,
        payload.grupo_prefixo, payload.seq_exemplo, payload.cor_codigo, payload.tam_codigo,
    )
    return {"data": PreviewResponse(codigo_gerado=codigo), "error": None}
