import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models.painel_vendedor import Catalogo, CatalogoVendedor
from models.venda import TabelaPreco

router = APIRouter(prefix="/api/v1/catalogos", tags=["catalogos"])

_UPLOAD_DIR = "uploads/catalogos"


@router.get("/")
def listar(db: Session = Depends(get_db)):
    rows = db.execute(select(Catalogo).where(Catalogo.ativo == True)).scalars().all()
    result = []
    for cat in rows:
        tabela_nome = None
        if cat.tabela_preco_id:
            t = db.get(TabelaPreco, cat.tabela_preco_id)
            tabela_nome = t.nome if t else None
        result.append({
            "id": str(cat.id),
            "nome": cat.nome,
            "tabela_preco_id": str(cat.tabela_preco_id) if cat.tabela_preco_id else None,
            "tabela_preco_nome": tabela_nome,
            "arquivo_path": cat.arquivo_path,
        })
    return {"data": result, "error": None}


@router.post("/")
async def criar(
    nome: str = Form(...),
    tabela_preco_id: Optional[str] = Form(None),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(arquivo.filename or "")[1] or ".pdf"
    path = os.path.join(_UPLOAD_DIR, f"{uuid.uuid4()}{ext}")
    with open(path, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)

    cat = Catalogo(
        nome=nome,
        tabela_preco_id=uuid.UUID(tabela_preco_id) if tabela_preco_id else None,
        arquivo_path=path,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {
        "data": {
            "id": str(cat.id),
            "nome": cat.nome,
            "tabela_preco_id": str(cat.tabela_preco_id) if cat.tabela_preco_id else None,
            "arquivo_path": cat.arquivo_path,
        },
        "error": None,
    }


@router.delete("/{catalogo_id}")
def deletar(catalogo_id: uuid.UUID, db: Session = Depends(get_db)):
    cat = db.get(Catalogo, catalogo_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Catálogo não encontrado")
    cat.ativo = False
    db.commit()
    return {"data": None, "error": None}


@router.get("/{catalogo_id}/vendedores")
def listar_vendedores(catalogo_id: uuid.UUID, db: Session = Depends(get_db)):
    acessos = (
        db.execute(select(CatalogoVendedor).where(CatalogoVendedor.catalogo_id == catalogo_id))
        .scalars()
        .all()
    )
    return {"data": [str(a.vendedor_id) for a in acessos], "error": None}


class VendedorAcessoInput(BaseModel):
    vendedor_id: uuid.UUID


@router.post("/{catalogo_id}/vendedores")
def add_vendedor(catalogo_id: uuid.UUID, payload: VendedorAcessoInput, db: Session = Depends(get_db)):
    exists = (
        db.query(CatalogoVendedor)
        .filter(
            CatalogoVendedor.catalogo_id == catalogo_id,
            CatalogoVendedor.vendedor_id == payload.vendedor_id,
        )
        .first()
    )
    if not exists:
        db.add(CatalogoVendedor(catalogo_id=catalogo_id, vendedor_id=payload.vendedor_id))
        db.commit()
    return {"data": None, "error": None}


@router.delete("/{catalogo_id}/vendedores/{vendedor_id}")
def remove_vendedor(catalogo_id: uuid.UUID, vendedor_id: uuid.UUID, db: Session = Depends(get_db)):
    acesso = (
        db.query(CatalogoVendedor)
        .filter(
            CatalogoVendedor.catalogo_id == catalogo_id,
            CatalogoVendedor.vendedor_id == vendedor_id,
        )
        .first()
    )
    if acesso:
        db.delete(acesso)
        db.commit()
    return {"data": None, "error": None}
