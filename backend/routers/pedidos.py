import calendar
import uuid
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from models.pedido import PedidoVenda
from schemas.pedido_schema import (
    AdicionarGrupoPecaCreate,
    PedidoCreate,
    PedidoStatusUpdate,
    PedidoTecidoCreate,
    PedidoUpdate,
)
from services import pedido_service
from services import report_service

router = APIRouter(prefix="/api/v1/pedidos", tags=["pedidos"])

_MOD = "pedidos"


# ── Métricas (dashboard) ──────────────────────────────────────────────

def _ultimos_meses(n: int) -> list[tuple[int, int]]:
    """Lista (ano, mes) dos últimos `n` meses, do mais antigo ao atual."""
    hoje = date.today()
    chaves = []
    m, a = hoje.month, hoje.year
    for _ in range(n):
        chaves.append((a, m))
        m -= 1
        if m == 0:
            m, a = 12, a - 1
    chaves.reverse()
    return chaves


def _serie_mensal_pedidos(db: Session, meses: int = 12) -> list[dict]:
    chaves = _ultimos_meses(meses)
    data_min = date(chaves[0][0], chaves[0][1], 1)

    rows = db.execute(
        select(
            func.strftime("%Y-%m", PedidoVenda.data_emissao).label("chave"),
            func.sum(PedidoVenda.total_pedido).label("total"),
        )
        .where(PedidoVenda.tipo == "venda", PedidoVenda.data_emissao >= data_min)
        .group_by("chave")
    ).all()
    mapa = {r.chave: float(r.total or 0) for r in rows}

    return [
        {"mes": m, "ano": a, "total": mapa.get(f"{a:04d}-{m:02d}", 0.0)}
        for a, m in chaves
    ]


def _serie_semanal_pedidos(db: Session, semanas: int = 8) -> list[dict]:
    hoje = date.today()
    data_min = hoje - timedelta(weeks=semanas)

    rows = db.execute(
        select(
            func.strftime("%Y-%W", PedidoVenda.data_emissao).label("chave"),
            func.sum(PedidoVenda.total_pedido).label("total"),
        )
        .where(PedidoVenda.tipo == "venda", PedidoVenda.data_emissao >= data_min)
        .group_by("chave")
    ).all()
    mapa = {r.chave: float(r.total or 0) for r in rows}

    chaves = []
    d = hoje
    for _ in range(semanas):
        chaves.append(d.strftime("%Y-%W"))
        d -= timedelta(weeks=1)
    chaves.reverse()

    return [{"semana": chave, "total": mapa.get(chave, 0.0)} for chave in chaves]


@router.get("/metricas", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def metricas(
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Métricas de desempenho de vendas para o dashboard executivo.

    total_faturado/total_pedidos/ticket_medio/top_clientes respeitam o
    período (data_inicio/data_fim, padrão: mês atual). As séries temporais
    (faturamento_por_mes/por_semana) são sempre a janela móvel mais recente,
    independente do período selecionado — são gráficos de tendência.
    """
    if not data_inicio or not data_fim:
        hoje = date.today()
        data_inicio = hoje.replace(day=1)
        data_fim = date(hoje.year, hoje.month, calendar.monthrange(hoje.year, hoje.month)[1])

    pedidos_periodo = db.execute(
        select(PedidoVenda).where(
            PedidoVenda.tipo == "venda",
            PedidoVenda.data_emissao >= data_inicio,
            PedidoVenda.data_emissao <= data_fim,
        )
    ).scalars().all()

    total_faturado = sum(float(p.total_pedido or 0) for p in pedidos_periodo)
    total_pedidos = len(pedidos_periodo)
    ticket_medio = (total_faturado / total_pedidos) if total_pedidos else 0.0

    clientes_map: dict[str, dict] = {}
    for p in pedidos_periodo:
        nome = p.cliente_razao_social or "—"
        agg = clientes_map.setdefault(nome, {"cliente": nome, "total_pedidos": 0, "total_valor": 0.0})
        agg["total_pedidos"] += 1
        agg["total_valor"] += float(p.total_pedido or 0)
    top_clientes = sorted(clientes_map.values(), key=lambda x: x["total_valor"], reverse=True)[:5]

    return {
        "data": {
            "total_faturado": total_faturado,
            "total_pedidos": total_pedidos,
            "ticket_medio": ticket_medio,
            "faturamento_por_mes": _serie_mensal_pedidos(db, meses=12),
            "top_clientes": top_clientes,
            "faturamento_por_semana": _serie_semanal_pedidos(db, semanas=8),
        },
        "error": None,
    }


# ── Rota fixa deve vir ANTES das rotas com parâmetro ─────────────────

@router.get(
    "/proximo-numero", response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "ver"))],
)
def proximo_numero(db: Session = Depends(get_db)):
    return {"data": {"numero": pedido_service.proximo_numero(db)}, "error": None}


@router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def listar_pedidos(db: Session = Depends(get_db)):
    return {"data": pedido_service.listar(db), "error": None}


@router.get("/{pedido_id}", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def obter_pedido(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    pedido = pedido_service.obter_detalhe(db, pedido_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": pedido, "error": None}


@router.post(
    "/", response_model=dict, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("pedidos_criar", "ver"))],
)
def criar_pedido(payload: PedidoCreate, db: Session = Depends(get_db)):
    try:
        pedido = pedido_service.criar(db, payload)
        return {"data": pedido, "error": None}
    except IntegrityError:
        db.rollback()
        sugestao = pedido_service.proximo_numero(db)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"O número de pedido já está em uso. Sugerimos o número: {sugestao}",
        )


@router.patch(
    "/{pedido_id}", response_model=dict,
    dependencies=[Depends(require_permission("pedidos_editar", "ver"))],
)
def atualizar_pedido(
    pedido_id: uuid.UUID, payload: PedidoUpdate, db: Session = Depends(get_db)
):
    pedido = pedido_service.atualizar(db, pedido_id, payload)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": pedido, "error": None}


@router.patch(
    "/{pedido_id}/status", response_model=dict,
    dependencies=[Depends(require_permission("pedidos_editar", "ver"))],
)
def alterar_status(
    pedido_id: uuid.UUID, payload: PedidoStatusUpdate, db: Session = Depends(get_db)
):
    pedido = pedido_service.alterar_status(db, pedido_id, payload)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": pedido, "error": None}


@router.delete(
    "/{pedido_id}", response_model=dict,
    dependencies=[Depends(require_permission("pedidos_excluir", "ver"))],
)
def excluir_pedido(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    ok = pedido_service.excluir(db, pedido_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": {"excluido": True}, "error": None}


@router.post(
    "/{pedido_id}/duplicar", response_model=dict, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("pedidos_criar", "ver"))],
)
def duplicar_pedido(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    novo = pedido_service.duplicar(db, pedido_id)
    if not novo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": novo, "error": None}


# ── Tecidos do pedido ─────────────────────────────────────────────────

@router.post(
    "/{pedido_id}/tecidos", response_model=dict, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("pedidos_editar", "ver"))],
)
def adicionar_tecido(
    pedido_id: uuid.UUID, payload: PedidoTecidoCreate, db: Session = Depends(get_db)
):
    pedido = pedido_service.adicionar_tecido(db, pedido_id, payload)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": pedido, "error": None}


@router.delete(
    "/{pedido_id}/tecidos/{pt_id}", response_model=dict,
    dependencies=[Depends(require_permission("pedidos_editar", "ver"))],
)
def remover_tecido(
    pedido_id: uuid.UUID, pt_id: uuid.UUID, db: Session = Depends(get_db)
):
    pedido = pedido_service.remover_tecido(db, pedido_id, pt_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": pedido, "error": None}


# ── Peças ─────────────────────────────────────────────────────────────

@router.post(
    "/{pedido_id}/pecas", response_model=dict, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("pedidos_editar", "ver"))],
)
def adicionar_grupo_pecas(
    pedido_id: uuid.UUID,
    payload: AdicionarGrupoPecaCreate,
    db: Session = Depends(get_db),
):
    pedido = pedido_service.adicionar_grupo_pecas(db, pedido_id, payload)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": pedido, "error": None}


@router.delete(
    "/{pedido_id}/pecas/{grupo_id}/{tamanho}", response_model=dict,
    dependencies=[Depends(require_permission("pedidos_editar", "ver"))],
)
def remover_grupo_pecas(
    pedido_id: uuid.UUID,
    grupo_id: uuid.UUID,
    tamanho: str,
    db: Session = Depends(get_db),
):
    pedido = pedido_service.remover_grupo_pecas(db, pedido_id, grupo_id, tamanho)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": pedido, "error": None}


# ── Resumo e relatório ────────────────────────────────────────────────

@router.get(
    "/{pedido_id}/resumo-corte", response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "ver"))],
)
def resumo_corte(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    resumo = pedido_service.calcular_resumo_corte(db, pedido_id)
    if not resumo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": resumo, "error": None}


@router.get(
    "/{pedido_id}/relatorio-pdf",
    dependencies=[Depends(require_permission(_MOD, "ver"))],
)
def relatorio_pdf(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    pedido = pedido_service.obter_detalhe(db, pedido_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    resumo = pedido_service.calcular_resumo_corte(db, pedido_id)
    pdf_bytes = report_service.gerar_pdf_pedido(pedido, resumo)
    num = pedido["num_pedido"].replace("/", "-").replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="pedido-{num}.pdf"'},
    )
