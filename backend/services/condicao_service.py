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


def _dias_intervalo(condicao: str) -> list[int]:
    """Dias da condição do tipo "intervalo": "30/60/90" → [30, 60, 90];
    "X3:30" → [30, 60, 90]; vazia → [0] (à vista)."""
    texto = condicao.strip()
    m = _X_PATTERN.match(texto)
    if m:
        n, intervalo = int(m.group(1)), int(m.group(2))
        if n <= 0:
            raise ValueError("Quantidade de parcelas deve ser maior que zero.")
        return [intervalo * i for i in range(1, n + 1)]

    tokens = [t.strip() for t in texto.split("/") if t.strip() != ""]
    if not tokens:
        return [0]
    try:
        dias = [int(t) for t in tokens]
    except ValueError as e:
        raise ValueError(f"Condição de pagamento inválida (intervalo): '{condicao}'") from e
    if any(d < 0 for d in dias):
        raise ValueError(f"Condição de pagamento inválida (intervalo): '{condicao}'")
    return dias


def _vencimentos_intervalo(condicao: str, data_emissao: date, primeiro_vencimento: date | None = None) -> list[date]:
    """Sem primeiro_vencimento: parcela k = emissão + dk dias.

    Com primeiro_vencimento, ele É a 1ª parcela e as demais mantêm a
    distância da condição em relação a d1:
      - todos os dias múltiplos de 30 → + (dk - d1) / 30 meses, mesmo dia do
        mês (ou o último dia, se o mês não tiver: 31/01 → 28/02);
      - senão → + (dk - d1) dias.
    """
    dias = _dias_intervalo(condicao)
    if primeiro_vencimento is None:
        return [data_emissao + timedelta(days=d) for d in dias]
    d1 = dias[0]
    if all(d % 30 == 0 for d in dias):
        # Sempre a partir do 1º vencimento (não encadeado): 31/01 → 28/02 → 31/03.
        return [_add_meses(primeiro_vencimento, (d - d1) // 30) for d in dias]
    return [primeiro_vencimento + timedelta(days=d - d1) for d in dias]


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
    condicao: CondicaoPagamento,
    valor_base: Decimal,
    data_emissao: date,
    primeiro_vencimento: date | None = None,
) -> list[dict]:
    """Gera a lista de parcelas de uma condição de pagamento aplicada sobre
    `valor_base` — ÚNICO lugar do cálculo (simulação da condição, prévia do
    pedido e qualquer geração futura de títulos chamam esta função).

    Datas são `date` puras (sem hora/fuso). primeiro_vencimento só vale para
    o tipo "intervalo" (ver _vencimentos_intervalo); o tipo "fixo" usa o dia
    fixo do mês a partir da emissão.

    Retorna [{"parcela": 1, "total": N, "valor": Decimal, "vencimento":
    date, "descricao": "1/N"}, ...]. Cada parcela = total / N truncado em 2
    casas; a diferença de centavos vai na 1ª, e a soma bate exatamente com o
    valor ajustado (R$ 100,00 em 3x → 33,34 | 33,33 | 33,33).
    """
    valor_base = Decimal(str(valor_base))
    ajuste_pct = (Decimal(str(condicao.acrescimo or 0)) - Decimal(str(condicao.desconto or 0))) / Decimal("100")
    valor_ajustado = (valor_base * (Decimal("1") + ajuste_pct)).quantize(Decimal("0.01"))

    condicao_texto = (condicao.condicao or "").strip()
    if condicao.tipo == "intervalo":
        vencimentos = _vencimentos_intervalo(condicao_texto, data_emissao, primeiro_vencimento)
    elif condicao.tipo == "fixo":
        vencimentos = _vencimentos_fixo(condicao_texto, data_emissao)
    else:
        raise ValueError(f"Tipo de condição inválido: {condicao.tipo}")

    n = len(vencimentos)
    if n == 0:
        raise ValueError("Condição de pagamento não gerou nenhuma parcela.")

    valor_parcela = (valor_ajustado / n).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    primeira = valor_ajustado - valor_parcela * (n - 1)
    parcelas = []
    for i, vencimento in enumerate(vencimentos, start=1):
        valor = primeira if i == 1 else valor_parcela
        parcelas.append(
            {
                "parcela": i,
                "total": n,
                "valor": valor,
                "vencimento": vencimento,
                "descricao": f"{i}/{n}",
            }
        )
    return parcelas
