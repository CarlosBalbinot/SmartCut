import re
from calendar import monthrange
from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal

from models.condicao_pagamento import CondicaoPagamento

# "X12:30" / "X12:10" — N parcelas iguais a um intervalo fixo (dias, para
# tipo "intervalo") ou a um dia fixo do mês (para tipo "fixo").
_X_PATTERN = re.compile(r"^[Xx](\d+):(\d+)$")


def _add_meses(d: date, meses: int) -> date:
    """Avança `d` em `meses` meses, respeitando o último dia de cada mês."""
    mes_total = d.month - 1 + meses
    ano = d.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = min(d.day, monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def _dia_fixo(data_emissao: date, dia: int, meses_offset: int) -> date:
    """Dia `dia` do mês que fica `meses_offset` meses à frente do mês de
    emissão. Se o dia não existir nesse mês (ex.: 31 em fevereiro), usa o
    último dia do mês (regra pedida explicitamente)."""
    ref = _add_meses(date(data_emissao.year, data_emissao.month, 1), meses_offset)
    ultimo_dia = monthrange(ref.year, ref.month)[1]
    dia_ajustado = min(max(dia, 1), ultimo_dia)
    return date(ref.year, ref.month, dia_ajustado)


def _vencimentos_intervalo(condicao: str, data_emissao: date) -> list[date]:
    m = _X_PATTERN.match(condicao.strip())
    if m:
        n, intervalo = int(m.group(1)), int(m.group(2))
        if n <= 0:
            raise ValueError("Quantidade de parcelas deve ser maior que zero.")
        return [data_emissao + timedelta(days=intervalo * i) for i in range(1, n + 1)]

    tokens = [t.strip() for t in condicao.split("/") if t.strip() != ""]
    if not tokens:
        raise ValueError("Condição de pagamento vazia.")
    try:
        return [data_emissao + timedelta(days=int(t)) for t in tokens]
    except ValueError as e:
        raise ValueError(f"Condição de pagamento inválida (intervalo): '{condicao}'") from e


def _vencimentos_fixo(condicao: str, data_emissao: date) -> list[date]:
    m = _X_PATTERN.match(condicao.strip())
    if m:
        n, dia = int(m.group(1)), int(m.group(2))
        if n <= 0:
            raise ValueError("Quantidade de parcelas deve ser maior que zero.")
        return [_dia_fixo(data_emissao, dia, i) for i in range(1, n + 1)]

    tokens = [t.strip() for t in condicao.split("/") if t.strip() != ""]
    if not tokens:
        raise ValueError("Condição de pagamento vazia.")

    vencimentos = []
    try:
        for i, token in enumerate(tokens, start=1):
            if ":" in token:
                dia_str, offset_str = token.split(":", 1)
                dia, offset = int(dia_str), int(offset_str)
            else:
                # Sem offset explícito: 1ª parcela no mês seguinte, 2ª no
                # próximo, e assim por diante — ex.: "10/15/10".
                dia, offset = int(token), i
            vencimentos.append(_dia_fixo(data_emissao, dia, offset))
    except ValueError as e:
        raise ValueError(f"Condição de pagamento inválida (fixo): '{condicao}'") from e
    return vencimentos


def gerar_parcelas(
    condicao: CondicaoPagamento, valor_base: Decimal, data_emissao: date
) -> list[dict]:
    """Gera a lista de parcelas de uma condição de pagamento aplicada sobre
    `valor_base`, a partir de `data_emissao`.

    Retorna [{"parcela": 1, "total": N, "valor": Decimal, "vencimento":
    date, "descricao": "1/N"}, ...]. A última parcela absorve a diferença
    de arredondamento, para que a soma bata exatamente com o valor ajustado.
    """
    valor_base = Decimal(str(valor_base))
    ajuste_pct = (
        Decimal(str(condicao.acrescimo or 0)) - Decimal(str(condicao.desconto or 0))
    ) / Decimal("100")
    valor_ajustado = (valor_base * (Decimal("1") + ajuste_pct)).quantize(Decimal("0.01"))

    condicao_texto = (condicao.condicao or "").strip()
    if condicao.tipo == "intervalo":
        vencimentos = _vencimentos_intervalo(condicao_texto, data_emissao)
    elif condicao.tipo == "fixo":
        vencimentos = _vencimentos_fixo(condicao_texto, data_emissao)
    else:
        raise ValueError(f"Tipo de condição inválido: {condicao.tipo}")

    n = len(vencimentos)
    if n == 0:
        raise ValueError("Condição de pagamento não gerou nenhuma parcela.")

    valor_parcela = (valor_ajustado / n).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    parcelas = []
    acumulado = Decimal("0.00")
    for i, vencimento in enumerate(vencimentos, start=1):
        if i < n:
            valor = valor_parcela
            acumulado += valor
        else:
            valor = valor_ajustado - acumulado
        parcelas.append({
            "parcela": i,
            "total": n,
            "valor": valor,
            "vencimento": vencimento,
            "descricao": f"{i}/{n}",
        })
    return parcelas
