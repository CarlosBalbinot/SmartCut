import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_db
from models.grupo_molde import GrupoMolde
from models.venda import PrecoReferencia, TabelaPreco
from schemas.venda_schema import (
    TabelaPrecoCreate, TabelaPrecoItemCreate, TabelaPrecoItemOut,
    TabelaPrecoOut, TabelaPrecoUpdate,
)

router = APIRouter(prefix="/api/v1/tabelas-preco", tags=["tabelas_preco"])


@router.get("/")
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


@router.post("/")
def criar(payload: TabelaPrecoCreate, db: Session = Depends(get_db)):
    tabela = TabelaPreco(**payload.model_dump())
    db.add(tabela)
    db.commit()
    db.refresh(tabela)
    return {"data": TabelaPrecoOut.model_validate(tabela), "error": None}


@router.get("/{tabela_id}/itens")
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
        )
        for pr, gm in rows
    ]
    return {"data": result, "error": None}


@router.post("/{tabela_id}/itens")
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
    else:
        db.add(PrecoReferencia(
            tabela_id=tabela_id,
            grupo_id=payload.grupo_id,
            preco_avista=payload.preco_avista,
            preco_aprazo=payload.preco_aprazo,
        ))
    db.commit()
    return {"data": None, "error": None}


@router.delete("/{tabela_id}/itens/{grupo_id}")
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


@router.get("/{tabela_id}")
def get_one(tabela_id: uuid.UUID, db: Session = Depends(get_db)):
    tabela = db.get(TabelaPreco, tabela_id)
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    return {"data": TabelaPrecoOut.model_validate(tabela), "error": None}


@router.patch("/{tabela_id}")
def atualizar(tabela_id: uuid.UUID, payload: TabelaPrecoUpdate, db: Session = Depends(get_db)):
    tabela = db.get(TabelaPreco, tabela_id)
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(tabela, field, val)
    db.commit()
    db.refresh(tabela)
    return {"data": TabelaPrecoOut.model_validate(tabela), "error": None}


@router.delete("/{tabela_id}")
def deletar(tabela_id: uuid.UUID, db: Session = Depends(get_db)):
    tabela = db.get(TabelaPreco, tabela_id)
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    db.delete(tabela)
    db.commit()
    return {"data": None, "error": None}
