import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.tecido_schema import CorOut, CorUpdate, LoteCreate, LoteOut
from services import cor_service, lote_service

router = APIRouter(prefix="/api/v1/cores-tecido", tags=["cores-tecido"])


@router.get("/{cor_id}", response_model=dict)
def obter_cor(cor_id: uuid.UUID, db: Session = Depends(get_db)):
    cor = cor_service.obter(db, cor_id)
    if not cor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cor não encontrada")
    return {"data": cor, "error": None}


@router.patch("/{cor_id}", response_model=dict)
def atualizar_cor(cor_id: uuid.UUID, payload: CorUpdate, db: Session = Depends(get_db)):
    cor = cor_service.atualizar(db, cor_id, payload)
    if not cor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cor não encontrada")
    return {"data": cor, "error": None}


@router.delete("/{cor_id}", response_model=dict)
def deletar_cor(cor_id: uuid.UUID, db: Session = Depends(get_db)):
    ok = cor_service.deletar(db, cor_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cor não encontrada")
    return {"data": {"deleted": True}, "error": None}


# ── Lotes de uma cor ──────────────────────────────────────────────────

@router.get("/{cor_id}/lotes", response_model=dict)
def listar_lotes(cor_id: uuid.UUID, db: Session = Depends(get_db)):
    lotes = lote_service.listar_por_cor(db, cor_id)
    return {"data": lotes, "error": None}


@router.post("/{cor_id}/lotes", response_model=dict, status_code=status.HTTP_201_CREATED)
def criar_lote(cor_id: uuid.UUID, payload: LoteCreate, db: Session = Depends(get_db)):
    lote = lote_service.criar(db, cor_id, payload)
    return {"data": lote, "error": None}


@router.get("/{cor_id}/recomendar-lote", response_model=dict)
def recomendar_lote(cor_id: uuid.UUID, db: Session = Depends(get_db)):
    lote = cor_service.recomendar_lote(db, cor_id)
    return {"data": lote, "error": None}
