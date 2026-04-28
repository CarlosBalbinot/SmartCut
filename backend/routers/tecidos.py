import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.tecido_schema import TecidoCreate, TecidoOut, TecidoUpdate
from services import tecido_service

router = APIRouter(prefix="/api/v1/tecidos", tags=["tecidos"])


@router.get("/", response_model=dict)
def listar_tecidos(db: Session = Depends(get_db)):
    tecidos = tecido_service.listar(db)
    return {"data": tecidos, "error": None}


@router.get("/{tecido_id}", response_model=dict)
def obter_tecido(tecido_id: uuid.UUID, db: Session = Depends(get_db)):
    tecido = tecido_service.obter(db, tecido_id)
    if not tecido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tecido não encontrado")
    return {"data": tecido, "error": None}


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def criar_tecido(payload: TecidoCreate, db: Session = Depends(get_db)):
    tecido = tecido_service.criar(db, payload)
    return {"data": tecido, "error": None}


@router.patch("/{tecido_id}", response_model=dict)
def atualizar_tecido(
    tecido_id: uuid.UUID, payload: TecidoUpdate, db: Session = Depends(get_db)
):
    tecido = tecido_service.atualizar(db, tecido_id, payload)
    if not tecido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tecido não encontrado")
    return {"data": tecido, "error": None}


@router.delete("/{tecido_id}", response_model=dict)
def deletar_tecido(tecido_id: uuid.UUID, db: Session = Depends(get_db)):
    ok = tecido_service.deletar(db, tecido_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tecido não encontrado")
    return {"data": {"deleted": True}, "error": None}
