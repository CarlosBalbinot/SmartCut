import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from schemas.molde_schema import BulkImportCreate, MoldeUpdate
from services import molde_service

router = APIRouter(prefix="/api/v1/moldes", tags=["moldes"])

_MOD = "moldes"


@router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def listar_moldes(db: Session = Depends(get_db)):
    moldes = molde_service.listar(db)
    return {"data": moldes, "error": None}


@router.get("/{molde_id}", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def obter_molde(molde_id: uuid.UUID, db: Session = Depends(get_db)):
    molde = molde_service.obter(db, molde_id)
    if not molde:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Molde não encontrado")
    return {"data": molde, "error": None}


@router.post(
    "/preview", response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
async def preview_molde(arquivo: UploadFile = File(...)):
    """Recebe o arquivo, extrai as peças e retorna o preview sem salvar no banco."""
    try:
        resultado = await molde_service.preview_arquivo(arquivo)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return {"data": resultado, "error": None}


@router.post(
    "/bulk", response_model=dict, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
def importar_bulk(payload: BulkImportCreate, db: Session = Depends(get_db)):
    """Salva no banco todas as peças confirmadas pelo usuário."""
    moldes = molde_service.importar_bulk(db, payload)
    return {"data": moldes, "error": None}


@router.patch(
    "/{molde_id}", response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "editar"))],
)
def atualizar_molde(
    molde_id: uuid.UUID,
    dados: MoldeUpdate,
    db: Session = Depends(get_db),
):
    molde = molde_service.atualizar(db, molde_id, dados)
    if not molde:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Molde não encontrado")
    return {"data": molde, "error": None}


@router.delete(
    "/{molde_id}", response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "excluir"))],
)
def deletar_molde(molde_id: uuid.UUID, db: Session = Depends(get_db)):
    ok = molde_service.deletar(db, molde_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Molde não encontrado")
    return {"data": {"deleted": True}, "error": None}
