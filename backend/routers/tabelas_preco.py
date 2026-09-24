import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from middleware.permissions import get_current_user, require_permission
from models.grupo_molde import GrupoMolde
from models.produto import Produto
from models.produto_sku import ProdutoSKU
from models.usuario import Permissao, Usuario
from models.venda import PrecoReferencia, PrecoTabelaProduto, TabelaPreco
from schemas.venda_schema import TabelaPrecoItemCreate, TabelaPrecoItemOut

router = APIRouter(prefix="/api/v1/tabelas-preco", tags=["tabelas_preco"])

# Tabelas de preço são geridas no painel de Configurações.
# configuracoes_ver/configuracoes_editar são módulos próprios em
# MODULOS_VALIDOS — a ação passada é sempre "ver" (única ação hoje
# verificada em todo o sistema).
_MOD_VER = "configuracoes_ver"
_MOD_EDITAR = "configuracoes_editar"


def _pode_listar(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Usuario:
    """configuracoes_ver OU pedidos_ver — a tela de pedido precisa listar as
    tabelas para o seletor sem dar acesso às Configurações."""
    if current_user.is_admin:
        return current_user
    tem = db.execute(
        select(Permissao.id).where(
            Permissao.usuario_id == current_user.id,
            Permissao.modulo.in_((_MOD_VER, "pedidos_ver")),
            Permissao.acao == "ver",
            Permissao.permitido == True,  # noqa: E712
        )
    ).first()
    if not tem:
        raise HTTPException(status_code=403, detail="Você não tem permissão para listar tabelas de preço.")
    return current_user


# ── Schemas inline ────────────────────────────────────────────────────────────
# Sem comissao_pct: a comissão agora é por vendedor + tabela
# (VendedorTabelaComissao). Se o cliente ainda mandar o campo, é ignorado.


class _TabelaPrecoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nome: str
    ativa: bool
    criado_em: datetime


class _TabelaPrecoCreate(BaseModel):
    nome: str


class _TabelaPrecoUpdate(BaseModel):
    nome: Optional[str] = None
    ativa: Optional[bool] = None


@router.get("/", dependencies=[Depends(_pode_listar)])
def listar(db: Session = Depends(get_db)):
    rows = db.execute(select(TabelaPreco).order_by(TabelaPreco.nome)).scalars().all()
    counts_raw = db.execute(
        select(PrecoReferencia.tabela_id, func.count(PrecoReferencia.id)).group_by(PrecoReferencia.tabela_id)
    ).all()
    counts = {tabela_id: cnt for tabela_id, cnt in counts_raw}
    result = []
    for r in rows:
        d = _TabelaPrecoOut.model_validate(r).model_dump()
        d["num_itens"] = counts.get(r.id, 0)
        result.append(d)
    return {"data": result, "error": None}


@router.post("/", dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))])
def criar(payload: _TabelaPrecoCreate, db: Session = Depends(get_db)):
    tabela = TabelaPreco(**payload.model_dump())
    db.add(tabela)
    db.commit()
    db.refresh(tabela)
    return {"data": _TabelaPrecoOut.model_validate(tabela), "error": None}


@router.get("/{tabela_id}/itens", dependencies=[Depends(require_permission(_MOD_VER, "ver"))])
def listar_itens(tabela_id: uuid.UUID, db: Session = Depends(get_db)):
    tabela = db.get(TabelaPreco, tabela_id)
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    rows = db.execute(
        select(PrecoReferencia, GrupoMolde)
        .join(GrupoMolde, PrecoReferencia.grupo_id == GrupoMolde.id)
        .where(PrecoReferencia.tabela_id == tabela_id)
        .order_by(GrupoMolde.codigo.nullslast(), GrupoMolde.nome)
    ).all()
    result = [
        TabelaPrecoItemOut(
            grupo_id=pr.grupo_id,
            codigo=gm.codigo,
            nome=gm.nome,
            preco_avista=pr.preco_avista,
            preco_aprazo=pr.preco_aprazo,
            tem_plus_size=pr.tem_plus_size,
            preco_avista_plus=pr.preco_avista_plus,
            preco_aprazo_plus=pr.preco_aprazo_plus,
        )
        for pr, gm in rows
    ]
    return {"data": result, "error": None}


@router.post("/{tabela_id}/itens", dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))])
def upsert_item(tabela_id: uuid.UUID, payload: TabelaPrecoItemCreate, db: Session = Depends(get_db)):
    tabela = db.get(TabelaPreco, tabela_id)
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    existing = (
        db.execute(
            select(PrecoReferencia).where(
                PrecoReferencia.tabela_id == tabela_id,
                PrecoReferencia.grupo_id == payload.grupo_id,
            )
        )
        .scalars()
        .first()
    )
    if existing:
        existing.preco_avista = payload.preco_avista
        existing.preco_aprazo = payload.preco_aprazo
        existing.tem_plus_size = payload.tem_plus_size or False
        existing.preco_avista_plus = payload.preco_avista_plus
        existing.preco_aprazo_plus = payload.preco_aprazo_plus
    else:
        db.add(
            PrecoReferencia(
                tabela_id=tabela_id,
                grupo_id=payload.grupo_id,
                preco_avista=payload.preco_avista,
                preco_aprazo=payload.preco_aprazo,
                tem_plus_size=payload.tem_plus_size or False,
                preco_avista_plus=payload.preco_avista_plus,
                preco_aprazo_plus=payload.preco_aprazo_plus,
            )
        )
    db.commit()
    return {"data": None, "error": None}


@router.delete(
    "/{tabela_id}/itens/{grupo_id}",
    dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))],
)
def remover_item(tabela_id: uuid.UUID, grupo_id: uuid.UUID, db: Session = Depends(get_db)):
    existing = (
        db.execute(
            select(PrecoReferencia).where(
                PrecoReferencia.tabela_id == tabela_id,
                PrecoReferencia.grupo_id == grupo_id,
            )
        )
        .scalars()
        .first()
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    db.delete(existing)
    db.commit()
    return {"data": None, "error": None}


# ── Preços por produto pai / SKU (precos_tabela_produto) ─────────────────────
# Convivem com os preços por grupo acima (PrecoReferencia, legado). Na
# resolução do preço do item (venda_service.resolver_preco_item) o preço do
# SKU vence o do produto pai, que vence o do grupo.


class _PrecoProdutoIn(BaseModel):
    produto_id: Optional[uuid.UUID] = None
    sku_id: Optional[int] = None
    preco_avista: Decimal = Field(..., ge=0)
    preco_aprazo: Decimal = Field(..., ge=0)
    tem_plus_size: bool = False
    preco_avista_plus: Optional[Decimal] = Field(None, ge=0)
    preco_aprazo_plus: Optional[Decimal] = Field(None, ge=0)

    @model_validator(mode="after")
    def _produto_xor_sku(self):
        if (self.produto_id is None) == (self.sku_id is None):
            raise ValueError("Informe exatamente um entre produto_id e sku_id.")
        return self


_CAMPOS_PRECO = (
    "preco_avista",
    "preco_aprazo",
    "tem_plus_size",
    "preco_avista_plus",
    "preco_aprazo_plus",
)


def _preco_produto_out(pp: PrecoTabelaProduto) -> dict:
    if pp.sku_id is not None:
        sku = pp.sku
        pai = sku.produto_pai if sku else None
        partes = [
            pai.descricao if pai else "",
            sku.linha_item_descricao if sku else None,
            sku.coluna_item_descricao if sku else None,
        ]
        tipo, codigo = "SKU", sku.codigo if sku else None
        descricao = " ".join(p for p in partes if p)
        produto_pai_id = sku.produto_pai_id if sku else None
    else:
        tipo = "PRODUTO"
        codigo = pp.produto.codigo if pp.produto else None
        descricao = pp.produto.descricao if pp.produto else ""
        produto_pai_id = pp.produto_id
    return {
        "id": pp.id,
        "tipo": tipo,
        "produto_id": pp.produto_id,
        "sku_id": pp.sku_id,
        "produto_pai_id": produto_pai_id,
        "codigo": codigo,
        "descricao": descricao,
        **{c: getattr(pp, c) for c in _CAMPOS_PRECO},
    }


def _listar_precos_produto(db: Session, tabela_id: uuid.UUID) -> list[dict]:
    rows = (
        db.execute(
            select(PrecoTabelaProduto)
            .where(PrecoTabelaProduto.tabela_preco_id == tabela_id)
            .options(
                selectinload(PrecoTabelaProduto.produto),
                selectinload(PrecoTabelaProduto.sku).selectinload(ProdutoSKU.produto_pai),
                selectinload(PrecoTabelaProduto.sku).selectinload(ProdutoSKU.linha_item),
                selectinload(PrecoTabelaProduto.sku).selectinload(ProdutoSKU.coluna_item),
            )
        )
        .scalars()
        .all()
    )
    # Produto pai seguido dos próprios SKUs, em ordem de código.
    itens = [_preco_produto_out(pp) for pp in rows]
    itens.sort(
        key=lambda i: (
            str(i["produto_pai_id"] or ""),
            i["tipo"] != "PRODUTO",
            i["codigo"] or "",
        )
    )
    return itens


@router.get(
    "/{tabela_id}/precos-produto",
    dependencies=[Depends(require_permission(_MOD_VER, "ver"))],
)
def listar_precos_produto(tabela_id: uuid.UUID, db: Session = Depends(get_db)):
    if not db.get(TabelaPreco, tabela_id):
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    return {"data": _listar_precos_produto(db, tabela_id), "error": None}


@router.put(
    "/{tabela_id}/precos-produto",
    dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))],
)
def upsert_precos_produto(
    tabela_id: uuid.UUID,
    payload: List[_PrecoProdutoIn] = Body(...),
    db: Session = Depends(get_db),
):
    """Upsert em lote — tudo ou nada: qualquer linha inválida recusa o lote."""
    if not db.get(TabelaPreco, tabela_id):
        raise HTTPException(status_code=404, detail="Tabela não encontrada")

    # Chave local evita duplicar a mesma linha dentro do lote (a sessão roda
    # com autoflush=False, então o SELECT não enxergaria o que foi adicionado).
    pendentes: dict[tuple, PrecoTabelaProduto] = {}
    for idx, linha in enumerate(payload, start=1):
        if linha.produto_id is not None:
            produto = db.get(Produto, linha.produto_id)
            if not produto:
                raise HTTPException(status_code=422, detail=f"Linha {idx}: produto não encontrado.")
            if not produto.is_pai:
                raise HTTPException(
                    status_code=422,
                    detail=f"Linha {idx}: {produto.codigo} não é produto pai (não tem SKUs).",
                )
            chave = ("produto", linha.produto_id)
            filtro = PrecoTabelaProduto.produto_id == linha.produto_id
        else:
            sku = db.get(ProdutoSKU, linha.sku_id)
            if not sku:
                raise HTTPException(status_code=422, detail=f"Linha {idx}: SKU não encontrado.")
            if sku.situacao != "Ativo":
                raise HTTPException(status_code=422, detail=f"Linha {idx}: SKU {sku.codigo} está inativo.")
            chave = ("sku", linha.sku_id)
            filtro = PrecoTabelaProduto.sku_id == linha.sku_id

        registro = (
            pendentes.get(chave)
            or db.execute(
                select(PrecoTabelaProduto).where(
                    PrecoTabelaProduto.tabela_preco_id == tabela_id,
                    filtro,
                )
            )
            .scalars()
            .first()
        )
        if registro is None:
            registro = PrecoTabelaProduto(
                tabela_preco_id=tabela_id,
                produto_id=linha.produto_id,
                sku_id=linha.sku_id,
            )
            db.add(registro)
        for campo in _CAMPOS_PRECO:
            setattr(registro, campo, getattr(linha, campo))
        if not registro.tem_plus_size:
            registro.preco_avista_plus = None
            registro.preco_aprazo_plus = None
        pendentes[chave] = registro

    db.commit()
    return {"data": _listar_precos_produto(db, tabela_id), "error": None}


@router.delete(
    "/{tabela_id}/precos-produto/{preco_id}",
    dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))],
)
def remover_preco_produto(tabela_id: uuid.UUID, preco_id: int, db: Session = Depends(get_db)):
    registro = db.get(PrecoTabelaProduto, preco_id)
    if not registro or registro.tabela_preco_id != tabela_id:
        raise HTTPException(status_code=404, detail="Preço não encontrado")
    db.delete(registro)
    db.commit()
    return {"data": None, "error": None}


@router.get("/{tabela_id}", dependencies=[Depends(require_permission(_MOD_VER, "ver"))])
def get_one(tabela_id: uuid.UUID, db: Session = Depends(get_db)):
    tabela = db.get(TabelaPreco, tabela_id)
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    return {"data": _TabelaPrecoOut.model_validate(tabela), "error": None}


@router.patch("/{tabela_id}", dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))])
def atualizar(tabela_id: uuid.UUID, payload: _TabelaPrecoUpdate, db: Session = Depends(get_db)):
    tabela = db.get(TabelaPreco, tabela_id)
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(tabela, field, val)
    db.commit()
    db.refresh(tabela)
    return {"data": _TabelaPrecoOut.model_validate(tabela), "error": None}


@router.delete("/{tabela_id}", dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))])
def deletar(tabela_id: uuid.UUID, db: Session = Depends(get_db)):
    tabela = db.get(TabelaPreco, tabela_id)
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    db.delete(tabela)
    db.commit()
    return {"data": None, "error": None}
