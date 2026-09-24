from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from models.tes import TES

router = APIRouter(prefix="/api/v1/tes", tags=["tes"])

_MOD = "fiscal_nfe"


# ── Schemas ─────────────────────────────────────────────────────────────


class TESCreate(BaseModel):
    codigo: str = Field(..., max_length=20)
    descricao: str = Field(..., max_length=200)
    tipo: str
    natureza_operacao: str = Field(..., max_length=200)
    cfop: str = Field(..., max_length=10)
    csosn: str = Field(..., max_length=3)
    cst_icms: Optional[str] = Field(None, max_length=2)
    origem: str = Field(..., max_length=1)
    modalidade_bc_icms: str = Field(..., max_length=1)
    reducao_bc_icms: float = 0.0
    aliquota_icms: float = 0.0
    valor_icms: float = 0.0
    pis_cst: str = Field(..., max_length=2)
    pis_aliquota: float = 0.0
    cofins_cst: str = Field(..., max_length=2)
    cofins_aliquota: float = 0.0
    gera_financeiro: bool = True
    movimenta_estoque: bool = True
    situacao: str = "Ativo"


class TESUpdate(BaseModel):
    codigo: Optional[str] = Field(None, max_length=20)
    descricao: Optional[str] = Field(None, max_length=200)
    tipo: Optional[str] = None
    natureza_operacao: Optional[str] = Field(None, max_length=200)
    cfop: Optional[str] = Field(None, max_length=10)
    csosn: Optional[str] = Field(None, max_length=3)
    cst_icms: Optional[str] = Field(None, max_length=2)
    origem: Optional[str] = Field(None, max_length=1)
    modalidade_bc_icms: Optional[str] = Field(None, max_length=1)
    reducao_bc_icms: Optional[float] = None
    aliquota_icms: Optional[float] = None
    valor_icms: Optional[float] = None
    pis_cst: Optional[str] = Field(None, max_length=2)
    pis_aliquota: Optional[float] = None
    cofins_cst: Optional[str] = Field(None, max_length=2)
    cofins_aliquota: Optional[float] = None
    gera_financeiro: Optional[bool] = None
    movimenta_estoque: Optional[bool] = None
    situacao: Optional[str] = None


class TESResponse(BaseModel):
    id: int
    codigo: str
    descricao: str
    tipo: str
    natureza_operacao: str
    cfop: str
    csosn: str
    cst_icms: Optional[str] = None
    origem: str
    modalidade_bc_icms: str
    reducao_bc_icms: float
    aliquota_icms: float
    valor_icms: float
    pis_cst: str
    pis_aliquota: float
    cofins_cst: str
    cofins_aliquota: float
    gera_financeiro: bool
    movimenta_estoque: bool
    situacao: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Rotas ───────────────────────────────────────────────────────────────


@router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def listar_tes(db: Session = Depends(get_db)):
    rows = db.query(TES).order_by(TES.codigo).all()
    return {"data": [TESResponse.model_validate(r) for r in rows], "error": None}


def buscar_tes_por_codigo(db: Session, codigo: str) -> TES | None:
    """Busca por código digitado — trim + case-insensitive. Usado também
    pela edição inline de itens em routers/pedidos_venda.py."""
    codigo = (codigo or "").strip()
    if not codigo:
        return None
    return db.query(TES).filter(func.lower(TES.codigo) == codigo.lower()).first()


# Declarada antes de /{tes_id}: senão "validar" cai na rota com path param
# int e volta 422 em vez de chegar aqui.
@router.get("/validar", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def validar_tes(codigo: str, db: Session = Depends(get_db)):
    tes = buscar_tes_por_codigo(db, codigo)
    if not tes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código de TES inválido")
    return {"data": {"id": tes.id, "codigo": tes.codigo, "descricao": tes.descricao}, "error": None}


@router.get("/{tes_id}", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def obter_tes(tes_id: int, db: Session = Depends(get_db)):
    tes = db.get(TES, tes_id)
    if not tes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TES não encontrado")
    return {"data": TESResponse.model_validate(tes), "error": None}


@router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
def criar_tes(payload: TESCreate, db: Session = Depends(get_db)):
    tes = TES(**payload.model_dump())
    db.add(tes)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Código já está em uso.")
    db.refresh(tes)
    return {"data": TESResponse.model_validate(tes), "error": None}


@router.put(
    "/{tes_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "editar"))],
)
def atualizar_tes(tes_id: int, payload: TESUpdate, db: Session = Depends(get_db)):
    tes = db.get(TES, tes_id)
    if not tes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TES não encontrado")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(tes, campo, valor)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Código já está em uso.")
    db.refresh(tes)
    return {"data": TESResponse.model_validate(tes), "error": None}


@router.delete(
    "/{tes_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "excluir"))],
)
def excluir_tes(tes_id: int, db: Session = Depends(get_db)):
    tes = db.get(TES, tes_id)
    if not tes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TES não encontrado")
    db.delete(tes)
    db.commit()
    return {"data": {"excluido": True}, "error": None}
