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

Camadas pares (camadas_pares=True): enfesto duplo com peças em par —
cada par de camadas corta a direita e a esquerda, então as camadas de cada
enfesto são arredondadas para o PAR acima (ou abaixo, se passar do máximo).
Um tamanho com menos peças que as camadas arredondadas entra com 1 conjunto
e a diferença vira sobra (registrada em sobra_por_tamanho).
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


def camadas_par(camadas: int, max_camadas: int) -> int:
    """Camadas arredondadas para o par acima; passando do máximo, o par
    abaixo. Com máximo 1 não há par possível (devolve 1 — quem chama não
    oferece enfesto duplo nesse caso)."""
    if camadas % 2 == 0:
        return camadas
    if camadas + 1 <= max_camadas:
        return camadas + 1
    return camadas - 1 if camadas > 1 else camadas


def _sem_sobra(qtds: dict[Hashable, int], max_camadas: int, pares: bool = False) -> list[dict]:
    restante = dict(qtds)
    enfestos: list[dict] = []
    while any(q > 0 for q in restante.values()):
        camadas = min(max_camadas, min(q for q in restante.values() if q > 0))
        if pares:
            camadas = camadas_par(camadas, max_camadas)
        conjuntos = {k: q // camadas for k, q in restante.items() if q >= camadas}
        if pares:
            # Camadas arredondadas para cima: o tamanho que ficou abaixo
            # entra com 1 conjunto e sobra a diferença.
            conjuntos.update({k: 1 for k, q in restante.items() if 0 < q < camadas})
        pedidas = {k: min(restante[k], camadas * c) for k, c in conjuntos.items()}
        for k, c in conjuntos.items():
            restante[k] = max(0, restante[k] - camadas * c)
        # Sem camadas pares a sobra é sempre 0: cada tamanho só entra com o
        # que cabe inteiro nas camadas (floor) — o resto vai para o próximo
        # enfesto.
        enfestos.append(_enfesto(camadas, conjuntos, pedidas))
    return enfestos


def _menos_enfestos(qtds: dict[Hashable, int], max_camadas: int, pares: bool = False) -> list[dict]:
    camadas = min(max_camadas, max(qtds.values()))
    if pares:
        camadas = camadas_par(camadas, max_camadas)
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


def planejar(
    quantidades_por_tamanho: dict[Hashable, int],
    max_camadas: int,
    modo: str = "SEM_SOBRA",
    *,
    camadas_pares: bool = False,
) -> dict:
    """Retorna {"modo", "camadas_pares", "enfestos": [{camadas,
    conjuntos_por_tamanho, pecas_por_tamanho, sobra_por_tamanho}],
    "pecas_por_tamanho", "sobra_por_tamanho", "sobra_total"} — totais somam
    todos os enfestos. camadas_pares: ver o topo do módulo (enfesto duplo)."""
    if modo not in MODOS:
        raise ValueError(f"Modo de camadas inválido: {modo}")
    qtds = {k: int(q) for k, q in quantidades_por_tamanho.items() if q and int(q) > 0}
    max_camadas = max(1, int(max_camadas or 1))
    if not qtds:
        enfestos: list[dict] = []
    elif modo == "SEM_SOBRA":
        enfestos = _sem_sobra(qtds, max_camadas, camadas_pares)
    else:
        enfestos = _menos_enfestos(qtds, max_camadas, camadas_pares)

    pecas = {k: 0 for k in qtds}
    for e in enfestos:
        for k, n in e["pecas_por_tamanho"].items():
            pecas[k] += n
    sobra = {k: pecas[k] - qtds[k] for k in qtds}
    return {
        "modo": modo,
        "camadas_pares": camadas_pares,
        "enfestos": enfestos,
        "pecas_por_tamanho": pecas,
        "sobra_por_tamanho": sobra,
        "sobra_total": sum(sobra.values()),
    }
