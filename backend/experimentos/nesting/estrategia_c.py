"""Estratégia C — faixa única + corte em trechos <= limite.

C1 "corte único": encaixa tudo numa faixa sem limite e fatia essa faixa.
   Cada trecho começa na peça mais baixa ainda não atribuída e leva as
   peças que terminam até início + limite; a peça que cruza a linha de
   corte fica para o trecho seguinte (que começa nela) — nenhuma peça é
   cortada e nada é reencaixado.
C2 "corte + reencaixe": igual, mas depois de fechar cada trecho o que
   sobrou (inclusive o que cruzava a linha) é reencaixado numa faixa nova.

Pares (tipo_corte par/par_sem_espelho) ficam inteiros no mesmo trecho,
como no motor atual: cópia ímpar sai do trecho (a mais alta).
"""

from __future__ import annotations

from collections.abc import Callable

from .comum import EPS, normalizar_parte

Faixa = Callable[[list[dict]], list[dict]]  # peças (com quantity) → parte posicionada


def _ymin(pc):
    return min(p[1] for p in pc["points"])


def _ymax(pc):
    return max(p[1] for p in pc["points"])


def _fechar_pares(dentro: list[dict], pares: set[str]) -> list[dict]:
    dentro = sorted(dentro, key=_ymax)
    for pid in pares:
        do_id = [pc for pc in dentro if pc["id"] == pid]
        if len(do_id) % 2:
            dentro.remove(do_id[-1])
    return dentro


def _trecho(faixa: list[dict], limite: float, pares: set[str]) -> list[dict]:
    """Peças do primeiro trecho da faixa (começando na peça mais baixa)."""
    y0 = min(_ymin(pc) for pc in faixa)
    dentro = [pc for pc in faixa if _ymax(pc) <= y0 + limite + EPS]
    dentro = _fechar_pares(dentro, pares)
    if not dentro:  # só meio par coube — leva o par inteiro (passa do limite)
        primeiro = min(faixa, key=_ymax)
        dentro = [primeiro]
        if primeiro["id"] in pares:
            dentro += sorted((pc for pc in faixa if pc["id"] == primeiro["id"] and pc is not primeiro), key=_ymax)[:1]
    return dentro


def c1_corte_unico(pecas: list[dict], faixa_fn: Faixa, limite: float, pares: set[str]) -> list[list[dict]]:
    faixa = faixa_fn(pecas)
    partes = []
    while faixa:
        dentro = _trecho(faixa, limite, pares)
        ids = {id(pc) for pc in dentro}
        faixa = [pc for pc in faixa if id(pc) not in ids]
        partes.append(normalizar_parte(dentro))
    return partes


def c2_corte_reencaixe(pecas: list[dict], faixa_fn: Faixa, limite: float, pares: set[str]) -> list[list[dict]]:
    restante = {p["id"]: p["quantity"] for p in pecas}
    por_id = {p["id"]: p for p in pecas}
    partes = []
    while any(restante.values()):
        lote = [{**por_id[i], "quantity": q} for i, q in restante.items() if q > 0]
        faixa = faixa_fn(lote)
        dentro = _trecho(faixa, limite, pares)
        for pc in dentro:
            restante[pc["id"]] -= 1
        partes.append(normalizar_parte(dentro))
    return partes
