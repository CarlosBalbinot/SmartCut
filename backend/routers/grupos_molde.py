import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.molde_schema import GrupoImportCreate, GrupoMoldeUpdate
from services import grupo_service

router = APIRouter(prefix="/api/v1/grupos-molde", tags=["grupos-molde"])


@router.get("/", response_model=dict)
def listar_grupos(db: Session = Depends(get_db)):
    grupos = grupo_service.listar(db)
    return {"data": grupos, "error": None}


@router.get("/{grupo_id}", response_model=dict)
def obter_grupo(grupo_id: uuid.UUID, db: Session = Depends(get_db)):
    grupo = grupo_service.obter(db, grupo_id)
    if not grupo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo não encontrado")
    return {"data": grupo, "error": None}


@router.post("/importar", response_model=dict, status_code=status.HTTP_201_CREATED)
def importar_grupo(payload: GrupoImportCreate, db: Session = Depends(get_db)):
    """Cria o grupo e todos os moldes de todas as partes em uma transação."""
    grupo = grupo_service.importar_grupo(db, payload)
    return {"data": grupo, "error": None}


@router.patch("/{grupo_id}", response_model=dict)
def renomear_grupo(
    grupo_id: uuid.UUID,
    dados: GrupoMoldeUpdate,
    db: Session = Depends(get_db),
):
    grupo = grupo_service.renomear(db, grupo_id, dados)
    if not grupo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo não encontrado")
    return {"data": grupo, "error": None}


@router.delete("/{grupo_id}", response_model=dict)
def deletar_grupo(grupo_id: uuid.UUID, db: Session = Depends(get_db)):
    ok = grupo_service.deletar(db, grupo_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo não encontrado")
    return {"data": {"deleted": True}, "error": None}
