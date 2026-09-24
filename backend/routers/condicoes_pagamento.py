from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from models.condicao_pagamento import SITUACAO_VALIDAS, TIPO_VALIDOS, CondicaoPagamento
from services.condicao_service import gerar_parcelas

router = APIRouter(prefix="/api/v1/condicoes-pagamento", tags=["condicoes_pagamento"])

_MOD_VER = "configuracoes_ver"
_MOD_EDITAR = "configuracoes_editar"


# ── Schemas ─────────────────────────────────────────────────────────────


class CondicaoPagamentoCreate(BaseModel):
    codigo: str = Field(..., max_length=10)
    descricao: str = Field(..., max_length=100)
    tipo: str
    condicao: str = Field(..., max_length=70)
    acrescimo: Decimal = Decimal("0")
    desconto: Decimal = Decimal("0")
    situacao: str = "Ativa"


class CondicaoPagamentoUpdate(BaseModel):
    codigo: Optional[str] = Field(None, max_length=10)
    descricao: Optional[str] = Field(None, max_length=100)
    tipo: Optional[str] = None
    condicao: Optional[str] = Field(None, max_length=70)
    acrescimo: Optional[Decimal] = None
    desconto: Optional[Decimal] = None
    situacao: Optional[str] = None


class CondicaoPagamentoResponse(BaseModel):
    id: int
    codigo: str
    descricao: str
    tipo: str
    condicao: str
    acrescimo: Decimal
    desconto: Decimal
    situacao: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SimularParcelasRequest(BaseModel):
    # condicao_id: simula uma condição já salva (uso típico: tela de
    # Pedido, onde o usuário escolhe uma condição existente).
    # tipo/condicao/acrescimo/desconto: simula valores ainda não salvos
    # (uso típico: modal de criar/editar Condição de Pagamento, para
    # mostrar o preview enquanto o usuário digita) — se informados,
    # têm prioridade sobre condicao_id.
    condicao_id: Optional[int] = None
    tipo: Optional[str] = None
    condicao: Optional[str] = None
    acrescimo: Decimal = Decimal("0")
    desconto: Decimal = Decimal("0")
    valor: Decimal
    data_emissao: date


class ParcelaSimuladaOut(BaseModel):
    parcela: int
    total: int
    valor: Decimal
    vencimento: date
    descricao: str


class SimularParcelasResponse(BaseModel):
    parcelas: list[ParcelaSimuladaOut]


# ── Helpers ─────────────────────────────────────────────────────────────


def _validar_tipo_situacao(tipo: str, situacao: str) -> None:
    if tipo not in TIPO_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Tipo inválido: {tipo}. Use {' ou '.join(TIPO_VALIDOS)}.")
    if situacao not in SITUACAO_VALIDAS:
        raise HTTPException(
            status_code=400,
            detail=f"Situação inválida: {situacao}. Use {' ou '.join(SITUACAO_VALIDAS)}.",
        )


def _get_ou_404(db: Session, condicao_id: int) -> CondicaoPagamento:
    condicao = db.get(CondicaoPagamento, condicao_id)
    if not condicao:
        raise HTTPException(status_code=404, detail="Condição de pagamento não encontrada")
    return condicao


# ── Rotas ───────────────────────────────────────────────────────────────


@router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD_VER, "ver"))])
def listar(situacao: Optional[str] = None, db: Session = Depends(get_db)):
    q = select(CondicaoPagamento)
    if situacao:
        if situacao not in SITUACAO_VALIDAS:
            raise HTTPException(status_code=400, detail=f"Situação inválida: {situacao}")
        q = q.where(CondicaoPagamento.situacao == situacao)
    q = q.order_by(CondicaoPagamento.codigo)
    rows = db.execute(q).scalars().all()
    return {"data": [CondicaoPagamentoResponse.model_validate(r) for r in rows], "error": None}


@router.get(
    "/{condicao_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD_VER, "ver"))],
)
def obter(condicao_id: int, db: Session = Depends(get_db)):
    condicao = _get_ou_404(db, condicao_id)
    return {"data": CondicaoPagamentoResponse.model_validate(condicao), "error": None}


@router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))],
)
def criar(payload: CondicaoPagamentoCreate, db: Session = Depends(get_db)):
    _validar_tipo_situacao(payload.tipo, payload.situacao)
    condicao = CondicaoPagamento(**payload.model_dump())
    db.add(condicao)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Código já está em uso.")
    db.refresh(condicao)
    return {"data": CondicaoPagamentoResponse.model_validate(condicao), "error": None}


@router.put(
    "/{condicao_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))],
)
def atualizar(condicao_id: int, payload: CondicaoPagamentoUpdate, db: Session = Depends(get_db)):
    condicao = _get_ou_404(db, condicao_id)
    dados = payload.model_dump(exclude_unset=True)
    _validar_tipo_situacao(dados.get("tipo", condicao.tipo), dados.get("situacao", condicao.situacao))
    for campo, valor in dados.items():
        setattr(condicao, campo, valor)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Código já está em uso.")
    db.refresh(condicao)
    return {"data": CondicaoPagamentoResponse.model_validate(condicao), "error": None}


@router.delete(
    "/{condicao_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))],
)
def excluir(condicao_id: int, db: Session = Depends(get_db)):
    condicao = _get_ou_404(db, condicao_id)
    db.delete(condicao)
    db.commit()
    return {"data": {"excluido": True}, "error": None}


@router.post(
    "/simular",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD_VER, "ver"))],
)
def simular(payload: SimularParcelasRequest, db: Session = Depends(get_db)):
    if payload.tipo and payload.condicao:
        # Preview ad-hoc (condição ainda não salva) — não toca o banco.
        _validar_tipo_situacao(payload.tipo, "Ativa")
        condicao = CondicaoPagamento(
            tipo=payload.tipo,
            condicao=payload.condicao,
            acrescimo=payload.acrescimo,
            desconto=payload.desconto,
        )
    elif payload.condicao_id is not None:
        condicao = _get_ou_404(db, payload.condicao_id)
    else:
        raise HTTPException(
            status_code=400,
            detail="Informe condicao_id ou tipo+condicao para simular.",
        )
    try:
        parcelas = gerar_parcelas(condicao, payload.valor, payload.data_emissao)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    resposta = SimularParcelasResponse(parcelas=[ParcelaSimuladaOut(**p) for p in parcelas])
    return {"data": resposta, "error": None}
