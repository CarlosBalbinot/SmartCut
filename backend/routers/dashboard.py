from calendar import monthrange
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from models.financeiro import CompraFinanceira
from models.pedido import PedidoVenda

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

_VER = require_permission("financeiro_painel", "ver")

MESES_PT = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]

TIPOS_FRETE_A_PAGAR = ("CIF", "Por conta de terceiros")


@router.get("/resumo", dependencies=[Depends(_VER)])
def resumo(db: Session = Depends(get_db)):
    hoje = date.today()
    inicio_mes = hoje.replace(day=1)
    fim_mes = date(hoje.year, hoje.month, monthrange(hoje.year, hoje.month)[1])
    periodo = f"{MESES_PT[hoje.month - 1]} {hoje.year}"

    # ── Pedidos do mês ───────────────────────────────────────────────────
    pedidos_mes = (
        db.execute(
            select(PedidoVenda).where(
                PedidoVenda.data_emissao >= inicio_mes,
                PedidoVenda.data_emissao <= fim_mes,
            )
        )
        .scalars()
        .all()
    )

    total_mes = len(pedidos_mes)
    fechados_mes = [p for p in pedidos_mes if p.status == "Fechado"]
    notas_geradas = len(fechados_mes)
    valor_notas = sum(float(p.total_pedido or 0) for p in fechados_mes)

    # ── Frete a pagar do mês (CIF / por conta de terceiros, não cancelados) ──
    total_pagar_mes = sum(
        float(p.valor_frete or 0)
        for p in pedidos_mes
        if p.tipo_frete in TIPOS_FRETE_A_PAGAR and p.status != "Cancelado"
    )

    # ── Evolução semanal (pedidos do mês agrupados por semana) ────────────
    num_semanas = (fim_mes.day - 1) // 7 + 1
    semanas: dict[int, int] = {i: 0 for i in range(1, num_semanas + 1)}
    for p in pedidos_mes:
        semana_num = (p.data_emissao.day - 1) // 7 + 1
        semanas[semana_num] += 1
    evolucao_semanal = [{"semana": f"Semana {i}", "pedidos": semanas[i]} for i in range(1, num_semanas + 1)]

    # ── Compras por fornecedor no mês (todas, sem limite) ─────────────────
    # CompraFinanceira.fornecedor é string livre (sem FK para uma tabela de
    # fornecedores), então o agrupamento é feito pelo próprio texto.
    compras_mes = (
        db.execute(
            select(CompraFinanceira).where(
                CompraFinanceira.data_compra >= inicio_mes,
                CompraFinanceira.data_compra <= fim_mes,
            )
        )
        .scalars()
        .all()
    )
    fornecedor_map: dict[str, float] = {}
    for c in compras_mes:
        fornecedor_map[c.fornecedor] = fornecedor_map.get(c.fornecedor, 0.0) + float(c.valor_total or 0)
    compras_fornecedor = sorted(
        ({"nome": k, "valor": v} for k, v in fornecedor_map.items()),
        key=lambda x: x["valor"],
        reverse=True,
    )

    # ── Top 5 clientes por quantidade de pedidos — últimos 90 dias ────────
    data_inicio_top = hoje - timedelta(days=90)
    pedidos_90d = db.execute(select(PedidoVenda).where(PedidoVenda.data_emissao >= data_inicio_top)).scalars().all()
    cliente_map: dict[str, dict] = {}
    for p in pedidos_90d:
        nome = p.cliente_razao_social or "Sem nome"
        entry = cliente_map.setdefault(nome, {"qtd_pedidos": 0, "valor_total": 0.0})
        entry["qtd_pedidos"] += 1
        entry["valor_total"] += float(p.total_pedido or 0)
    top5_clientes = sorted(
        ({"nome": k, **v} for k, v in cliente_map.items()),
        key=lambda x: x["qtd_pedidos"],
        reverse=True,
    )[:5]

    return {
        "data": {
            "periodo": periodo,
            "pedidos": {
                "total_mes": total_mes,
                "notas_geradas": notas_geradas,
                "valor_notas": valor_notas,
            },
            "frete": {
                "total_pagar_mes": total_pagar_mes,
            },
            "evolucao_semanal": evolucao_semanal,
            "compras_fornecedor": compras_fornecedor,
            "top5_clientes": top5_clientes,
        },
        "error": None,
    }
