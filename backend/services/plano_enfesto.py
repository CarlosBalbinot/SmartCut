"""Plano de enfesto — quantas camadas e quantos conjuntos de cada tamanho
vão em cada enfesto de um mesmo lote de tecido.

Lógica pura (sem banco): trabalha com peças inteiras (peças de roupa, não
partes do molde). A chave de cada "tamanho" é livre (ex.: (grupo_id, "P"))
— o chamador decide como identificar; aqui só importa a quantidade.

Um enfesto com C camadas e k conjuntos de um tamanho corta C × k peças
daquele tamanho (k marcações do tamanho no encaixe, repetidas em C camadas).

Modos:
  SEM_SOBRA (padrão)  — corta exatamente a quantidade pedida, podendo usar
                        mais de um enfesto.
  MENOS_ENFESTOS      — um único enfesto (regra antiga do nesting),
                        camadas = min(max_camadas, maior quantidade); tamanhos
                        com quantidade menor saem com sobra.
"""

from __future__ import annotations

import math
from collections.abc import Hashable

MODOS = ("SEM_SOBRA", "MENOS_ENFESTOS")


def _enfesto(camadas: int, conjuntos: dict, pedidas: dict) -> dict:
    cortadas = {k: camadas * c for k, c in conjuntos.items()}
    return {
        "camadas": camadas,
        "conjuntos_por_tamanho": conjuntos,
        "pecas_por_tamanho": cortadas,
        "sobra_por_tamanho": {k: max(0, cortadas[k] - pedidas.get(k, 0)) for k in conjuntos},
    }


def _sem_sobra(qtds: dict[Hashable, int], max_camadas: int) -> list[dict]:
    restante = dict(qtds)
    enfestos: list[dict] = []
    while any(q > 0 for q in restante.values()):
        camadas = min(max_camadas, min(q for q in restante.values() if q > 0))
        conjuntos = {k: q // camadas for k, q in restante.items() if q >= camadas}
        for k, c in conjuntos.items():
            restante[k] -= camadas * c
        # Sobra é sempre 0 aqui: cada tamanho só entra com o que cabe
        # inteiro nas camadas (floor) — o resto vai para o próximo enfesto.
        enfestos.append(_enfesto(camadas, conjuntos, {k: camadas * c for k, c in conjuntos.items()}))
    return enfestos


def _menos_enfestos(qtds: dict[Hashable, int], max_camadas: int) -> list[dict]:
    camadas = min(max_camadas, max(qtds.values()))
    conjuntos = {k: math.ceil(q / camadas) for k, q in qtds.items()}
    return [_enfesto(camadas, conjuntos, qtds)]


def linhas_enfesto(enfesto: dict, rotulos: dict[Hashable, dict]) -> list[dict]:
    """Enfesto (ou plano inteiro, que tem as mesmas chaves de totais) em
    linhas JSON: [{**rotulo, conjuntos, pecas, sobra}] — as chaves livres
    do plano viram rótulos legíveis (ex.: {"grupo_nome", "tamanho"})."""
    conjuntos = enfesto.get("conjuntos_por_tamanho", {})
    return [
        {
            **rotulos.get(k, {"tamanho": str(k)}),
            "conjuntos": conjuntos.get(k),
            "pecas": pecas,
            "sobra": enfesto["sobra_por_tamanho"].get(k, 0),
        }
        for k, pecas in enfesto["pecas_por_tamanho"].items()
    ]


def planejar(quantidades_por_tamanho: dict[Hashable, int], max_camadas: int, modo: str = "SEM_SOBRA") -> dict:
    """Retorna {"modo", "enfestos": [{camadas, conjuntos_por_tamanho,
    pecas_por_tamanho, sobra_por_tamanho}], "pecas_por_tamanho",
    "sobra_por_tamanho", "sobra_total"} — totais somam todos os enfestos."""
    if modo not in MODOS:
        raise ValueError(f"Modo de camadas inválido: {modo}")
    qtds = {k: int(q) for k, q in quantidades_por_tamanho.items() if q and int(q) > 0}
    max_camadas = max(1, int(max_camadas or 1))
    if not qtds:
        enfestos: list[dict] = []
    elif modo == "SEM_SOBRA":
        enfestos = _sem_sobra(qtds, max_camadas)
    else:
        enfestos = _menos_enfestos(qtds, max_camadas)

    pecas = {k: 0 for k in qtds}
    for e in enfestos:
        for k, n in e["pecas_por_tamanho"].items():
            pecas[k] += n
    sobra = {k: pecas[k] - qtds[k] for k in qtds}
    return {
        "modo": modo,
        "enfestos": enfestos,
        "pecas_por_tamanho": pecas,
        "sobra_por_tamanho": sobra,
        "sobra_total": sum(sobra.values()),
    }
