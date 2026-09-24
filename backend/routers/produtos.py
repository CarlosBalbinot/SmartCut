import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from middleware.permissions import require_permission
from models.produto_sku import ProdutoSKU
from schemas.produto_schema import (
    GradeItemCreate,
    GradeItemOut,
    GradePedidoOut,
    GrupoProdutoCreate,
    GrupoProdutoOut,
    GrupoProdutoUpdate,
    ProdutoBuscaPedidoOut,
    ProdutoCreate,
    ProdutoListagemOut,
    ProdutoOut,
    ProdutoSkuOut,
    ProdutoUpdate,
    PropagarPrecoResponse,
    SkuGerarRequest,
    SkuSincronizarRequest,
    SkuSincronizarResponse,
    SkuUpdate,
)
from services import grade_service, grupo_produto_service, produto_service, sku_service

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
    busca: str | None = None,
    excluir_pais: bool = False,
    db: Session = Depends(get_db),
):
    if excluir_pais:
        itens = produto_service.listar_sellable(db, status=status_produto, grupo_id=grupo_id, busca=busca)
        return {"data": [ProdutoListagemOut(**item) for item in itens], "error": None}
    produtos = produto_service.listar(db, status=status_produto, grupo_id=grupo_id, busca=busca)
    return {"data": [ProdutoOut.model_validate(p) for p in produtos], "error": None}


# Rotas estáticas "/busca-pedido" e "/{produto_pai_id}/grade-pedido" ficam
# antes de "/{produto_id}" — caso contrário o FastAPI tentaria casar
# "busca-pedido" com o parâmetro uuid produto_id e devolveria 422.


@router.get(
    "/busca-pedido",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "ver"))],
)
def busca_pedido_produtos(q: str = "", db: Session = Depends(get_db)):
    if not q.strip():
        return {"data": [], "error": None}
    itens = produto_service.busca_pedido(db, q.strip())
    return {"data": [ProdutoBuscaPedidoOut(**item) for item in itens], "error": None}


@router.get(
    "/{produto_pai_id}/grade-pedido",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "ver"))],
)
def grade_pedido_produto(produto_pai_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        resultado = produto_service.grade_pedido(db, produto_pai_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"data": GradePedidoOut(**resultado), "error": None}


# ── SKUs para o pedido de venda (troca de SKU por código / lupa) ────────
# Declaradas antes de /{produto_id}: senão "skus" cai na rota com UUID.


def _sku_opts():
    return (
        selectinload(ProdutoSKU.produto_pai),
        selectinload(ProdutoSKU.linha_item),
        selectinload(ProdutoSKU.coluna_item),
    )


def buscar_sku_ativo_por_codigo(db: Session, codigo: str) -> ProdutoSKU | None:
    """SKU filho ativo pelo código digitado — trim + case-insensitive.
    Usado também pelo PATCH de item em routers/pedidos_venda.py."""
    codigo = (codigo or "").strip()
    if not codigo:
        return None
    return (
        db.execute(
            select(ProdutoSKU)
            .where(func.lower(ProdutoSKU.codigo) == codigo.lower(), ProdutoSKU.situacao == "Ativo")
            .options(*_sku_opts())
        )
        .scalars()
        .first()
    )


def _sku_out(sku: ProdutoSKU) -> dict:
    # Mesmas regras de produto_service.listar_sellable: descrição = pai +
    # linha + coluna; preço fora de tabela = preço manual do SKU > do pai.
    pai = sku.produto_pai
    partes = (pai.descricao, sku.linha_item_descricao, sku.coluna_item_descricao)
    return {
        "id": sku.id,
        "codigo": sku.codigo,
        "descricao_completa": " ".join(p for p in partes if p),
        "preco_venda": sku.preco_venda if sku.preco_manual else pai.preco_venda,
    }


@router.get(
    "/skus/validar",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "ver"))],
)
def validar_sku(codigo: str, db: Session = Depends(get_db)):
    sku = buscar_sku_ativo_por_codigo(db, codigo)
    if not sku:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código de produto inválido")
    return {"data": _sku_out(sku), "error": None}


@router.get(
    "/skus",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "ver"))],
)
def buscar_skus(
    busca: str = "",
    limit: int = Query(50, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Busca de SKUs filhos ativos por código ou descrição (pai + linha +
    coluna). Cada palavra digitada precisa aparecer em algum dos dois."""
    skus = db.execute(select(ProdutoSKU).where(ProdutoSKU.situacao == "Ativo").options(*_sku_opts())).scalars().all()
    termos = busca.lower().split()
    itens = []
    for sku in skus:
        out = _sku_out(sku)
        alvo = f"{out['codigo']} {out['descricao_completa']}".lower()
        if all(t in alvo for t in termos):
            itens.append(out)
    itens.sort(key=lambda i: i["codigo"])
    return {
        "data": {
            "itens": itens[offset : offset + limit],
            "total": len(itens),
            "limit": limit,
            "offset": offset,
        },
        "error": None,
    }


@router.get("/{produto_id}", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def obter_produto(produto_id: uuid.UUID, db: Session = Depends(get_db)):
    produto = produto_service.obter(db, produto_id)
    if not produto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
    return {"data": ProdutoOut.model_validate(produto), "error": None}


@router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
def criar_produto(payload: ProdutoCreate, db: Session = Depends(get_db)):
    try:
        produto = produto_service.criar(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"data": ProdutoOut.model_validate(produto), "error": None}


@router.put(
    "/{produto_id}",
    response_model=dict,
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
    "/{produto_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "excluir"))],
)
def excluir_produto(produto_id: uuid.UUID, db: Session = Depends(get_db)):
    ok = produto_service.deletar(db, produto_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
    return {"data": {"excluido": True}, "error": None}


# ── SKUs (produto filho / grade) ──────────────────────────────────────


@router.post(
    "/{produto_id}/skus/gerar",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
def gerar_skus_produto(produto_id: uuid.UUID, payload: SkuGerarRequest, db: Session = Depends(get_db)):
    try:
        skus = sku_service.gerar_skus(db, produto_id, [c.model_dump() for c in payload.combinacoes])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"data": [ProdutoSkuOut.model_validate(s) for s in skus], "error": None}


@router.post(
    "/{produto_id}/skus/sincronizar",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "editar"))],
)
def sincronizar_skus_produto(produto_id: uuid.UUID, payload: SkuSincronizarRequest, db: Session = Depends(get_db)):
    try:
        resultado = sku_service.sincronizar_skus(
            db,
            produto_id,
            [c.model_dump() for c in payload.combinacoes],
            payload.remover_sku_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"data": SkuSincronizarResponse(**resultado), "error": None}


@router.get(
    "/{produto_id}/skus/",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "ver"))],
)
def listar_skus_produto(produto_id: uuid.UUID, db: Session = Depends(get_db)):
    skus = db.query(ProdutoSKU).filter(ProdutoSKU.produto_pai_id == produto_id).order_by(ProdutoSKU.codigo).all()
    return {"data": [ProdutoSkuOut.model_validate(s) for s in skus], "error": None}


@router.patch(
    "/{produto_id}/skus/{sku_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "editar"))],
)
def atualizar_sku_produto(produto_id: uuid.UUID, sku_id: int, payload: SkuUpdate, db: Session = Depends(get_db)):
    sku = db.get(ProdutoSKU, sku_id)
    if not sku or sku.produto_pai_id != produto_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SKU não encontrado")
    dados = payload.model_dump(exclude_unset=True)
    if "preco_venda" in dados:
        dados["preco_manual"] = True
    for campo, valor in dados.items():
        setattr(sku, campo, valor)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Código já está em uso.")
    db.refresh(sku)
    return {"data": ProdutoSkuOut.model_validate(sku), "error": None}


@router.post(
    "/{produto_id}/propagar-preco",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "editar"))],
)
def propagar_preco_produto(produto_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        resultado = sku_service.propagar_preco_pai(db, produto_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"data": PropagarPrecoResponse(**resultado), "error": None}


@router.delete(
    "/{produto_id}/skus/{sku_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "excluir"))],
)
def excluir_sku_produto(produto_id: uuid.UUID, sku_id: int, db: Session = Depends(get_db)):
    resultado = sku_service.remover_skus(db, produto_id, [sku_id])
    if resultado["bloqueados"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SKU '{resultado['bloqueados'][0]}' possui movimentação e não pode ser excluído.",
        )
    if resultado["removidos"] == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SKU não encontrado")
    return {"data": {"excluido": True}, "error": None}


# ── Grupos de Produto ─────────────────────────────────────────────────


@grupos_router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def listar_grupos(situacao: str | None = None, db: Session = Depends(get_db)):
    grupos = grupo_produto_service.listar(db, situacao=situacao)
    return {"data": [GrupoProdutoOut.model_validate(g) for g in grupos], "error": None}


@grupos_router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
def criar_grupo(payload: GrupoProdutoCreate, db: Session = Depends(get_db)):
    grupo = grupo_produto_service.criar(db, payload)
    return {"data": GrupoProdutoOut.model_validate(grupo), "error": None}


@grupos_router.put(
    "/{grupo_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "editar"))],
)
def atualizar_grupo(grupo_id: uuid.UUID, payload: GrupoProdutoUpdate, db: Session = Depends(get_db)):
    grupo = grupo_produto_service.atualizar(db, grupo_id, payload)
    if not grupo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo não encontrado")
    return {"data": GrupoProdutoOut.model_validate(grupo), "error": None}


@grupos_router.delete(
    "/{grupo_id}",
    response_model=dict,
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
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
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
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
def criar_coluna(payload: GradeItemCreate, db: Session = Depends(get_db)):
    item = grade_service.criar_coluna(db, payload)
    return {"data": GradeItemOut.model_validate(item), "error": None}
