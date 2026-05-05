import os
import shutil

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from database import get_db
from schemas.venda_schema import EmpresaOut, EmpresaUpdate
from services.venda_service import get_ou_criar_empresa

router = APIRouter(prefix="/api/v1/empresa", tags=["empresa"])

_LOGO_DIR = "uploads/logos"


@router.get("/")
def get_empresa(db: Session = Depends(get_db)):
    return {"data": EmpresaOut.model_validate(get_ou_criar_empresa(db)), "error": None}


@router.patch("/")
def update_empresa(payload: EmpresaUpdate, db: Session = Depends(get_db)):
    empresa = get_ou_criar_empresa(db)
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(empresa, field, val)
    db.commit()
    db.refresh(empresa)
    return {"data": EmpresaOut.model_validate(empresa), "error": None}


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...), db: Session = Depends(get_db)):
    os.makedirs(_LOGO_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "logo.png")[1] or ".png"
    path = os.path.join(_LOGO_DIR, f"empresa_logo{ext}")
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    empresa = get_ou_criar_empresa(db)
    empresa.logo_path = os.path.abspath(path)
    db.commit()
    db.refresh(empresa)
    return {"data": EmpresaOut.model_validate(empresa), "error": None}
