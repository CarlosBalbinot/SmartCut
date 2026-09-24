import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from schemas.tecido_schema import CorCreate, ModeloCreate, ModeloUpdate
from services import cor_service, modelo_service

router = APIRouter(prefix="/api/v1/modelos-tecido", tags=["modelos-tecido"])

_MOD = "tecidos"


@router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def listar_modelos(db: Session = Depends(get_db)):
    return {"data": modelo_service.listar(db), "error": None}


@router.get("/{modelo_id}", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def obter_modelo(modelo_id: uuid.UUID, db: Session = Depends(get_db)):
    modelo = modelo_service.obter(db, modelo_id)
    if not modelo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modelo não encontrado")
    return {"data": modelo, "error": None}


@router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
def criar_modelo(payload: ModeloCreate, db: Session = Depends(get_db)):
    modelo = modelo_service.criar(db, payload)
    return {"data": modelo, "error": None}


@router.patch(
    "/{modelo_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "editar"))],
)
def atualizar_modelo(modelo_id: uuid.UUID, payload: ModeloUpdate, db: Session = Depends(get_db)):
    modelo = modelo_service.atualizar(db, modelo_id, payload)
    if not modelo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modelo não encontrado")
    return {"data": modelo, "error": None}


@router.delete(
    "/{modelo_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "excluir"))],
)
def deletar_modelo(modelo_id: uuid.UUID, db: Session = Depends(get_db)):
    ok = modelo_service.deletar(db, modelo_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modelo não encontrado")
    return {"data": {"deleted": True}, "error": None}


# ── Cores de um modelo ────────────────────────────────────────────────


@router.get(
    "/{modelo_id}/cores",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "ver"))],
)
def listar_cores(modelo_id: uuid.UUID, db: Session = Depends(get_db)):
    cores = cor_service.listar_por_modelo(db, modelo_id)
    return {"data": cores, "error": None}


@router.post(
    "/{modelo_id}/cores",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
def criar_cor(modelo_id: uuid.UUID, payload: CorCreate, db: Session = Depends(get_db)):
    cor = cor_service.criar(db, modelo_id, payload)
    return {"data": cor, "error": None}
