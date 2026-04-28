import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models.precificacao import ConfiguracaoEmpresa, ConfiguracaoCustosFixos, Precificacao
from schemas.precificacao_schema import (
    ConfiguracaoEmpresaOut,
    ConfiguracaoEmpresaUpdate,
    ConfiguracaoCustosFixosOut,
    ConfiguracaoCustosFixosUpdate,
    PrecificacaoCreate,
    PrecificacaoOut,
    PrecificacaoUpdate,
)
from services.precificacao_service import (
    calcular_precificacao,
    get_ou_criar_config,
    get_ou_criar_custos,
    recalcular_sugerido,
)

router = APIRouter(prefix="/api/v1", tags=["precificacao"])


# ── Configuração da empresa ──────────────────────────────────────────────

@router.get("/configuracao-empresa/")
def get_config(db: Session = Depends(get_db)):
    config = get_ou_criar_config(db)
    return {"data": ConfiguracaoEmpresaOut.model_validate(config), "error": None}


@router.patch("/configuracao-empresa/")
def update_config(payload: ConfiguracaoEmpresaUpdate, db: Session = Depends(get_db)):
    config = get_ou_criar_config(db)
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(config, field, val)
    db.commit()
    db.refresh(config)
    return {"data": ConfiguracaoEmpresaOut.model_validate(config), "error": None}


# ── Custos fixos ─────────────────────────────────────────────────────────

@router.get("/configuracao-custos-fixos/")
def get_custos(db: Session = Depends(get_db)):
    custos = get_ou_criar_custos(db)
    return {"data": ConfiguracaoCustosFixosOut.model_validate(custos), "error": None}


@router.patch("/configuracao-custos-fixos/")
def update_custos(payload: ConfiguracaoCustosFixosUpdate, db: Session = Depends(get_db)):
    custos = get_ou_criar_custos(db)
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(custos, field, val)
    db.commit()
    db.refresh(custos)
    return {"data": ConfiguracaoCustosFixosOut.model_validate(custos), "error": None}


# ── Precificações ────────────────────────────────────────────────────────

@router.get("/precificacoes/")
def listar(grupo_id: str | None = None, db: Session = Depends(get_db)):
    q = select(Precificacao).where(Precificacao.ativo == True)
    if grupo_id:
        q = q.where(Precificacao.grupo_id == uuid.UUID(grupo_id))
    rows = db.execute(q.order_by(Precificacao.tamanho)).scalars().all()
    return {"data": [PrecificacaoOut.model_validate(r) for r in rows], "error": None}


@router.post("/precificacoes/")
def upsert(payload: PrecificacaoCreate, db: Session = Depends(get_db)):
    existing = db.execute(
        select(Precificacao).where(
            Precificacao.grupo_id == payload.grupo_id,
            Precificacao.tamanho == payload.tamanho,
            Precificacao.ativo == True,
        )
    ).scalars().first()

    config = get_ou_criar_config(db)
    custos = get_ou_criar_custos(db)
    data = payload.model_dump()

    if existing:
        for k, v in data.items():
            setattr(existing, k, v)
        prec = existing
    else:
        prec = Precificacao(**data)
        db.add(prec)

    recalcular_sugerido(prec, config, custos)
    db.commit()
    db.refresh(prec)
    return {"data": PrecificacaoOut.model_validate(prec), "error": None}


@router.get("/precificacoes/{grupo_id}/calcular")
def calcular(grupo_id: uuid.UUID, db: Session = Depends(get_db)):
    config = get_ou_criar_config(db)
    custos = get_ou_criar_custos(db)
    precs = db.execute(
        select(Precificacao)
        .where(Precificacao.grupo_id == grupo_id, Precificacao.ativo == True)
        .order_by(Precificacao.tamanho)
    ).scalars().all()

    resultado = []
    for p in precs:
        calc = calcular_precificacao(p, config, custos)
        preco_final = float(p.preco_venda_final) if p.preco_venda_final else calc.get("preco_sugerido")
        resultado.append({
            "id": str(p.id),
            "tamanho": p.tamanho,
            "faixa_tamanho": p.faixa_tamanho,
            **calc,
            "preco_final": preco_final,
        })

    return {"data": resultado, "error": None}


@router.patch("/precificacoes/{precificacao_id}")
def update(
    precificacao_id: uuid.UUID,
    payload: PrecificacaoUpdate,
    db: Session = Depends(get_db),
):
    prec = db.get(Precificacao, precificacao_id)
    if not prec:
        raise HTTPException(status_code=404, detail="Precificação não encontrada")

    config = get_ou_criar_config(db)
    custos = get_ou_criar_custos(db)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(prec, k, v)

    recalcular_sugerido(prec, config, custos)
    db.commit()
    db.refresh(prec)
    return {"data": PrecificacaoOut.model_validate(prec), "error": None}


@router.delete("/precificacoes/{precificacao_id}")
def deletar(precificacao_id: uuid.UUID, db: Session = Depends(get_db)):
    prec = db.get(Precificacao, precificacao_id)
    if not prec:
        raise HTTPException(status_code=404, detail="Precificação não encontrada")
    prec.ativo = False
    db.commit()
    return {"data": None, "error": None}
