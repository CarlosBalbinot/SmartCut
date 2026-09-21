import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from models.grupo_molde import GrupoMolde
from models.venda import PrecoReferencia, TabelaPreco
from schemas.venda_schema import (
    TabelaPrecoCreate, TabelaPrecoItemCreate, TabelaPrecoItemOut,
    TabelaPrecoOut, TabelaPrecoUpdate,
)

router = APIRouter(prefix="/api/v1/tabelas-preco", tags=["tabelas_preco"])

# Tabelas de preço são geridas no painel de Configurações.
# configuracoes_ver/configuracoes_editar são módulos próprios em
# MODULOS_VALIDOS — a ação passada é sempre "ver" (única ação hoje
# verificada em todo o sistema).
_MOD_VER = "configuracoes_ver"
_MOD_EDITAR = "configuracoes_editar"


@router.get("/", dependencies=[Depends(require_permission(_MOD_VER, "ver"))])
def listar(db: Session = Depends(get_db)):
    rows = db.execute(select(TabelaPreco).order_by(TabelaPreco.nome)).scalars().all()
    counts_raw = db.execute(
        select(PrecoReferencia.tabela_id, func.count(PrecoReferencia.id))
        .group_by(PrecoReferencia.tabela_id)
    ).all()
    counts = {tabela_id: cnt for tabela_id, cnt in counts_raw}
    result = []
    for r in rows:
        d = TabelaPrecoOut.model_validate(r).model_dump()
        d["num_itens"] = counts.get(r.id, 0)
        result.append(d)
    return {"data": result, "error": None}


@router.post("/", dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))])
def criar(payload: TabelaPrecoCreate, db: Session = Depends(get_db)):
    tabela = TabelaPreco(**payload.model_dump())
    db.add(tabela)
    db.commit()
    db.refresh(tabela)
    return {"data": TabelaPrecoOut.model_validate(tabela), "error": None}


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
    existing = db.execute(
        select(PrecoReferencia).where(
            PrecoReferencia.tabela_id == tabela_id,
            PrecoReferencia.grupo_id == payload.grupo_id,
        )
    ).scalars().first()
    if existing:
        existing.preco_avista = payload.preco_avista
        existing.preco_aprazo = payload.preco_aprazo
        existing.tem_plus_size = payload.tem_plus_size or False
        existing.preco_avista_plus = payload.preco_avista_plus
        existing.preco_aprazo_plus = payload.preco_aprazo_plus
    else:
        db.add(PrecoReferencia(
            tabela_id=tabela_id,
            grupo_id=payload.grupo_id,
            preco_avista=payload.preco_avista,
            preco_aprazo=payload.preco_aprazo,
            tem_plus_size=payload.tem_plus_size or False,
            preco_avista_plus=payload.preco_avista_plus,
            preco_aprazo_plus=payload.preco_aprazo_plus,
        ))
    db.commit()
    return {"data": None, "error": None}


@router.delete(
    "/{tabela_id}/itens/{grupo_id}",
    dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))],
)
def remover_item(tabela_id: uuid.UUID, grupo_id: uuid.UUID, db: Session = Depends(get_db)):
    existing = db.execute(
        select(PrecoReferencia).where(
            PrecoReferencia.tabela_id == tabela_id,
            PrecoReferencia.grupo_id == grupo_id,
        )
    ).scalars().first()
    if not existing:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    db.delete(existing)
    db.commit()
    return {"data": None, "error": None}


@router.get("/{tabela_id}", dependencies=[Depends(require_permission(_MOD_VER, "ver"))])
def get_one(tabela_id: uuid.UUID, db: Session = Depends(get_db)):
    tabela = db.get(TabelaPreco, tabela_id)
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    return {"data": TabelaPrecoOut.model_validate(tabela), "error": None}


@router.patch("/{tabela_id}", dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))])
def atualizar(tabela_id: uuid.UUID, payload: TabelaPrecoUpdate, db: Session = Depends(get_db)):
    tabela = db.get(TabelaPreco, tabela_id)
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(tabela, field, val)
    db.commit()
    db.refresh(tabela)
    return {"data": TabelaPrecoOut.model_validate(tabela), "error": None}


@router.delete("/{tabela_id}", dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))])
def deletar(tabela_id: uuid.UUID, db: Session = Depends(get_db)):
    tabela = db.get(TabelaPreco, tabela_id)
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    db.delete(tabela)
    db.commit()
    return {"data": None, "error": None}
