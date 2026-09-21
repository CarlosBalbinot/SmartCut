import os
import shutil

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from schemas.venda_schema import EmpresaOut, EmpresaUpdate, EmpresaFiscalUpdate, TestarCertificadoIn
from services.venda_service import (
    atualizar_fiscal, empresa_fiscal_out, get_ou_criar_empresa, testar_certificado,
)

router = APIRouter(prefix="/api/v1/configuracao-empresa", tags=["empresa"])

_LOGO_DIR = "uploads/logos"
_MOD_VER = "configuracoes_ver"
_MOD_EDITAR = "configuracoes_editar"

# Única fonte da verdade para /api/v1/configuracao-empresa/ (dados
# cadastrais da empresa: razão social, CNPJ, endereço, logo). Antes
# competia com um path igual em routers/precificacoes.py — movido para
# /configuracao-precificacao/ lá, então este GET/PATCH agora são
# realmente os únicos a responder por este prefixo.

@router.get("/", dependencies=[Depends(require_permission(_MOD_VER, "ver"))])
def get_empresa(db: Session = Depends(get_db)):
    return {"data": EmpresaOut.model_validate(get_ou_criar_empresa(db)), "error": None}

@router.patch("/", dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))])
def update_empresa(payload: EmpresaUpdate, db: Session = Depends(get_db)):
    empresa = get_ou_criar_empresa(db)
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(empresa, field, val)
    db.commit()
    db.refresh(empresa)
    return {"data": EmpresaOut.model_validate(empresa), "error": None}

@router.patch("/logo", dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))])
async def upload_logo(logo: UploadFile = File(...), db: Session = Depends(get_db)):
    # Certifica que o diretório existe
    os.makedirs(_LOGO_DIR, exist_ok=True)

    # Extrai a extensão do arquivo enviado
    ext = os.path.splitext(logo.filename or "logo.png")[1] or ".png"
    path = os.path.join(_LOGO_DIR, f"empresa_logo{ext}")

    # Salva o arquivo no disco
    with open(path, "wb") as f:
        shutil.copyfileobj(logo.file, f)

    # Guarda o caminho relativo (usado como URL: /uploads/logos/...)
    empresa = get_ou_criar_empresa(db)
    empresa.logo_path = path.replace("\\", "/")
    db.commit()
    db.refresh(empresa)

    return {"data": EmpresaOut.model_validate(empresa), "error": None}


@router.get("/fiscal", dependencies=[Depends(require_permission(_MOD_VER, "ver"))])
def get_fiscal(db: Session = Depends(get_db)):
    empresa = get_ou_criar_empresa(db)
    return {"data": empresa_fiscal_out(empresa), "error": None}


@router.patch("/fiscal", dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))])
def update_fiscal(payload: EmpresaFiscalUpdate, db: Session = Depends(get_db)):
    empresa = get_ou_criar_empresa(db)
    atualizar_fiscal(db, empresa, payload.model_dump(exclude_unset=True))
    return {"data": empresa_fiscal_out(empresa), "error": None}


@router.post("/fiscal/testar-certificado", dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))])
def testar_certificado_route(payload: TestarCertificadoIn):
    return {"data": testar_certificado(payload.certificado_path, payload.certificado_senha), "error": None}
