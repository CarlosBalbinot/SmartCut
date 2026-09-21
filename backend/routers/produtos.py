import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from schemas.produto_schema import (
    GradeItemCreate,
    GradeItemOut,
    GrupoProdutoCreate,
    GrupoProdutoOut,
    GrupoProdutoUpdate,
    ProdutoCreate,
    ProdutoOut,
    ProdutoUpdate,
)
from services import grade_service, grupo_produto_service, produto_service

router = APIRouter(prefix="/api/v1/produtos", tags=["produtos"])
grupos_router = APIRouter(prefix="/api/v1/grupos-produto", tags=["grupos-produto"])
linhas_grade_router = APIRouter(prefix="/api/v1/linhas-grade", tags=["linhas-grade"])
colunas_grade_router = APIRouter(prefix="/api/v1/colunas-grade", tags=["colunas-grade"])

_MOD = "cadastros_produtos"


# ── Produtos ────────────────────────────────────────────────────────────

@router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def listar_produtos(
    status_produto: str | None = None,
    grupo_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    produtos = produto_service.listar(db, status=status_produto, grupo_id=grupo_id)
    return {"data": [ProdutoOut.model_validate(p) for p in produtos], "error": None}


@router.get("/{produto_id}", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def obter_produto(produto_id: uuid.UUID, db: Session = Depends(get_db)):
    produto = produto_service.obter(db, produto_id)
    if not produto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
    return {"data": ProdutoOut.model_validate(produto), "error": None}


@router.post(
    "/", response_model=dict, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
def criar_produto(payload: ProdutoCreate, db: Session = Depends(get_db)):
    try:
        produto = produto_service.criar(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"data": ProdutoOut.model_validate(produto), "error": None}


@router.put(
    "/{produto_id}", response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "editar"))],
)
def atualizar_produto(produto_id: uuid.UUID, payload: ProdutoUpdate, db: Session = Depends(get_db)):
    try:
        produto = produto_service.atualizar(db, produto_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not produto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
    return {"data": ProdutoOut.model_validate(produto), "error": None}


@router.delete(
    "/{produto_id}", response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "excluir"))],
)
def excluir_produto(produto_id: uuid.UUID, db: Session = Depends(get_db)):
    ok = produto_service.deletar(db, produto_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
    return {"data": {"excluido": True}, "error": None}


# ── Grupos de Produto ─────────────────────────────────────────────────

@grupos_router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def listar_grupos(situacao: str | None = None, db: Session = Depends(get_db)):
    grupos = grupo_produto_service.listar(db, situacao=situacao)
    return {"data": [GrupoProdutoOut.model_validate(g) for g in grupos], "error": None}


@grupos_router.post(
    "/", response_model=dict, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
def criar_grupo(payload: GrupoProdutoCreate, db: Session = Depends(get_db)):
    grupo = grupo_produto_service.criar(db, payload)
    return {"data": GrupoProdutoOut.model_validate(grupo), "error": None}


@grupos_router.put(
    "/{grupo_id}", response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "editar"))],
)
def atualizar_grupo(grupo_id: uuid.UUID, payload: GrupoProdutoUpdate, db: Session = Depends(get_db)):
    grupo = grupo_produto_service.atualizar(db, grupo_id, payload)
    if not grupo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo não encontrado")
    return {"data": GrupoProdutoOut.model_validate(grupo), "error": None}


@grupos_router.delete(
    "/{grupo_id}", response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "excluir"))],
)
def excluir_grupo(grupo_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        ok = grupo_produto_service.deletar(db, grupo_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo não encontrado")
    return {"data": {"excluido": True}, "error": None}


# ── Linhas de Grade ─────────────────────────────────────────────────────

@linhas_grade_router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def listar_linhas(situacao: str | None = None, db: Session = Depends(get_db)):
    linhas = grade_service.listar_linhas(db, situacao=situacao)
    return {"data": [GradeItemOut.model_validate(i) for i in linhas], "error": None}


@linhas_grade_router.post(
    "/", response_model=dict, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
def criar_linha(payload: GradeItemCreate, db: Session = Depends(get_db)):
    item = grade_service.criar_linha(db, payload)
    return {"data": GradeItemOut.model_validate(item), "error": None}


# ── Colunas de Grade ─────────────────────────────────────────────────────

@colunas_grade_router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def listar_colunas(situacao: str | None = None, db: Session = Depends(get_db)):
    colunas = grade_service.listar_colunas(db, situacao=situacao)
    return {"data": [GradeItemOut.model_validate(i) for i in colunas], "error": None}


@colunas_grade_router.post(
    "/", response_model=dict, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
def criar_coluna(payload: GradeItemCreate, db: Session = Depends(get_db)):
    item = grade_service.criar_coluna(db, payload)
    return {"data": GradeItemOut.model_validate(item), "error": None}
