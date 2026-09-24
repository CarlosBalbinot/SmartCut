from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from middleware.permissions import require_permission
from models.produto import Produto
from models.tabela_grade import SITUACAO_VALIDAS, ItemTabelaGrade, TabelaGrade

router = APIRouter(prefix="/api/v1/tabelas-grade", tags=["tabelas_grade"])

_MOD_VER = "configuracoes_ver"
_MOD_EDITAR = "configuracoes_editar"


# ── Schemas ─────────────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    codigo_curto: str = Field(..., max_length=4)
    descricao: str = Field(..., max_length=100)
    ordem: int = 0
    situacao: str = "Ativa"


class ItemUpdate(BaseModel):
    codigo_curto: Optional[str] = Field(None, max_length=4)
    descricao: Optional[str] = Field(None, max_length=100)
    ordem: Optional[int] = None
    situacao: Optional[str] = None


class ItemResponse(BaseModel):
    id: int
    tabela_id: int
    codigo_curto: str
    descricao: str
    ordem: int
    situacao: str

    model_config = {"from_attributes": True}


class TabelaGradeCreate(BaseModel):
    codigo: str = Field(..., max_length=10)
    descricao: str = Field(..., max_length=100)
    situacao: str = "Ativa"


class TabelaGradeUpdate(BaseModel):
    codigo: Optional[str] = Field(None, max_length=10)
    descricao: Optional[str] = Field(None, max_length=100)
    situacao: Optional[str] = None


class TabelaGradeResponse(BaseModel):
    id: int
    codigo: str
    descricao: str
    situacao: str
    created_at: datetime
    itens: list[ItemResponse] = []

    model_config = {"from_attributes": True}


# ── Helpers ─────────────────────────────────────────────────────────────

def _validar_situacao(situacao: str) -> None:
    if situacao not in SITUACAO_VALIDAS:
        raise HTTPException(
            status_code=400,
            detail=f"Situação inválida: {situacao}. Use {' ou '.join(SITUACAO_VALIDAS)}.",
        )


def _get_tabela_ou_404(db: Session, tabela_id: int) -> TabelaGrade:
    tabela = db.get(TabelaGrade, tabela_id)
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela de grade não encontrada")
    return tabela


def _get_item_ou_404(db: Session, tabela_id: int, item_id: int) -> ItemTabelaGrade:
    item = db.get(ItemTabelaGrade, item_id)
    if not item or item.tabela_id != tabela_id:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    return item


def _tabela_vinculada_a_produto(db: Session, tabela_id: int) -> bool:
    # produto.linha_grade_id / coluna_grade_id hoje apontam para os models
    # legados LinhaGrade/ColunaGrade (UUID), não para TabelaGrade (Integer)
    # — ver aviso no relatório final. A checagem já compara contra
    # tabela_id para funcionar sem alteração assim que produto.py passar a
    # referenciar TabelaGrade; até lá, nunca encontra vínculo.
    existe = db.query(Produto).filter(
        or_(Produto.linha_grade_id == tabela_id, Produto.coluna_grade_id == tabela_id)
    ).first()
    return existe is not None


def _item_usado_em_produto(item: ItemTabelaGrade) -> bool:
    # Ainda não existe model de "produto filho" (SKU por combinação de
    # grade) na base — nada referencia ItemTabelaGrade hoje. Retorna
    # sempre False até essa modelagem existir (próxima etapa).
    return False


# ── Tabelas de Grade ────────────────────────────────────────────────────

@router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD_VER, "ver"))])
def listar(situacao: Optional[str] = None, db: Session = Depends(get_db)):
    q = select(TabelaGrade).options(selectinload(TabelaGrade.itens))
    if situacao:
        _validar_situacao(situacao)
        q = q.where(TabelaGrade.situacao == situacao)
    q = q.order_by(TabelaGrade.codigo)
    rows = db.execute(q).scalars().all()
    return {"data": [TabelaGradeResponse.model_validate(r) for r in rows], "error": None}


@router.get(
    "/{tabela_id}", response_model=dict,
    dependencies=[Depends(require_permission(_MOD_VER, "ver"))],
)
def obter(tabela_id: int, db: Session = Depends(get_db)):
    tabela = _get_tabela_ou_404(db, tabela_id)
    return {"data": TabelaGradeResponse.model_validate(tabela), "error": None}


@router.post(
    "/", response_model=dict, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))],
)
def criar(payload: TabelaGradeCreate, db: Session = Depends(get_db)):
    _validar_situacao(payload.situacao)
    tabela = TabelaGrade(**payload.model_dump())
    db.add(tabela)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Código já está em uso.")
    db.refresh(tabela)
    return {"data": TabelaGradeResponse.model_validate(tabela), "error": None}


@router.put(
    "/{tabela_id}", response_model=dict,
    dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))],
)
def atualizar(tabela_id: int, payload: TabelaGradeUpdate, db: Session = Depends(get_db)):
    tabela = _get_tabela_ou_404(db, tabela_id)
    dados = payload.model_dump(exclude_unset=True)
    if "situacao" in dados:
        _validar_situacao(dados["situacao"])
    for campo, valor in dados.items():
        setattr(tabela, campo, valor)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Código já está em uso.")
    db.refresh(tabela)
    return {"data": TabelaGradeResponse.model_validate(tabela), "error": None}


@router.delete(
    "/{tabela_id}", response_model=dict,
    dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))],
)
def excluir(tabela_id: int, db: Session = Depends(get_db)):
    tabela = _get_tabela_ou_404(db, tabela_id)
    if _tabela_vinculada_a_produto(db, tabela_id):
        raise HTTPException(status_code=400, detail="Tabela vinculada a produtos e não pode ser excluída.")
    db.delete(tabela)
    db.commit()
    return {"data": {"excluido": True}, "error": None}


# ── Itens da Tabela de Grade ────────────────────────────────────────────

@router.get(
    "/{tabela_id}/itens/", response_model=dict,
    dependencies=[Depends(require_permission(_MOD_VER, "ver"))],
)
def listar_itens(tabela_id: int, db: Session = Depends(get_db)):
    _get_tabela_ou_404(db, tabela_id)
    itens = db.execute(
        select(ItemTabelaGrade)
        .where(ItemTabelaGrade.tabela_id == tabela_id)
        .order_by(ItemTabelaGrade.ordem, ItemTabelaGrade.descricao)
    ).scalars().all()
    return {"data": [ItemResponse.model_validate(i) for i in itens], "error": None}


@router.post(
    "/{tabela_id}/itens/", response_model=dict, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))],
)
def criar_item(tabela_id: int, payload: ItemCreate, db: Session = Depends(get_db)):
    _get_tabela_ou_404(db, tabela_id)
    _validar_situacao(payload.situacao)
    item = ItemTabelaGrade(tabela_id=tabela_id, **payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Código curto já está em uso nesta tabela.")
    db.refresh(item)
    return {"data": ItemResponse.model_validate(item), "error": None}


@router.put(
    "/{tabela_id}/itens/{item_id}", response_model=dict,
    dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))],
)
def atualizar_item(tabela_id: int, item_id: int, payload: ItemUpdate, db: Session = Depends(get_db)):
    item = _get_item_ou_404(db, tabela_id, item_id)
    dados = payload.model_dump(exclude_unset=True)
    if "situacao" in dados:
        _validar_situacao(dados["situacao"])
    for campo, valor in dados.items():
        setattr(item, campo, valor)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Código curto já está em uso nesta tabela.")
    db.refresh(item)
    return {"data": ItemResponse.model_validate(item), "error": None}


@router.delete(
    "/{tabela_id}/itens/{item_id}", response_model=dict,
    dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))],
)
def excluir_item(tabela_id: int, item_id: int, db: Session = Depends(get_db)):
    item = _get_item_ou_404(db, tabela_id, item_id)
    if _item_usado_em_produto(item):
        raise HTTPException(status_code=400, detail="Item já utilizado em produtos e não pode ser excluído.")
    db.delete(item)
    db.commit()
    return {"data": {"excluido": True}, "error": None}
