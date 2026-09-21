import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from schemas.tecido_schema import LoteOut, LoteUpdate
from services import lote_service

router = APIRouter(prefix="/api/v1/lotes-tecido", tags=["lotes-tecido"])

_MOD = "tecidos"


# ── Rotas fixas antes das rotas com parâmetro ─────────────────────────

@router.get("/alertas", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def alertas(db: Session = Depends(get_db)):
    return {"data": lote_service.verificar_alertas(db), "error": None}


@router.get("/historico", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def historico(db: Session = Depends(get_db)):
    lotes = lote_service.listar_historico(db)
    return {"data": lotes, "error": None}


@router.get(
    "/proximo-codigo", response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "ver"))],
)
def proximo_codigo(db: Session = Depends(get_db)):
    return {"data": {"codigo": lote_service.proximo_codigo(db)}, "error": None}


# ── CRUD por lote_id ──────────────────────────────────────────────────

@router.get("/{lote_id}", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def obter_lote(lote_id: uuid.UUID, db: Session = Depends(get_db)):
    lote = lote_service.obter(db, lote_id)
    if not lote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote não encontrado")
    return {"data": lote, "error": None}


@router.patch(
    "/{lote_id}", response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "editar"))],
)
def atualizar_lote(lote_id: uuid.UUID, payload: LoteUpdate, db: Session = Depends(get_db)):
    lote = lote_service.atualizar(db, lote_id, payload)
    if not lote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote não encontrado")
    return {"data": lote, "error": None}


@router.post(
    "/{lote_id}/arquivar", response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "editar"))],
)
def arquivar_lote(lote_id: uuid.UUID, db: Session = Depends(get_db)):
    lote = lote_service.arquivar(db, lote_id)
    if not lote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote não encontrado")
    return {"data": lote, "error": None}
