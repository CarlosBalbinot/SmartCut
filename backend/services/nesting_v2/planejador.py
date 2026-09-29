"""planejador.py — etapa 2: CP-SAT divide as peças do enfesto em K mesas.

O spyrrow resolve strip packing (minimizar o comprimento de UMA faixa, sem
teto de comprimento). Quem decide "quantas mesas e o que vai em cada uma" é o
CP-SAT, com uma restrição de área por mesa:

    capacidade = largura_cm × comprimento_max_cm × densidade_alvo

`densidade_alvo` é a fração da mesa que se espera preencher. Ela é o que
define K: o K mínimo é ceil(área_total / capacidade), então no K mínimo as
mesas saem quase cheias por construção. O objetivo é minimizar a CARGA MÁXIMA
(makespan): sem objetivo o solver entregava a primeira partição factível,
rotineiramente empilhando 16–18 mil cm² numa mesa (que nunca cabe no limite de
comprimento) e deixando outras quase vazias; minimizar o maior carregamento
equilibra as mesas em milissegundos e é o que faz o encaixe fechar cada uma
dentro do limite. Quem corrige o desequilíbrio residual — uma mesa que sobrou
cheia demais depois do balanceamento — é o ciclo de ajuste do motor.

Duas restrições que o enunciado pede explicitamente:

  * par — as duas metades de um par na MESMA mesa (igual ao v1, mas sem
    obrigar que fiquem na mesma posição);
  * proibidas — restrição EXTRA do ciclo de ajuste: a peça que estourou o
    limite da mesa t não pode voltar para t no próximo planejamento.

K mínimo viável, na ordem: começa no K que a área permite e SOBE de um em um
até o encaixe caber (motor.py faz essa escalada). Preferimos o K menor porque
cada mesa a mais é um pedaço de tecido no fim da mesa.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from services.nesting_v2.geometria import Unidade

# Segundos de CP-SAT por partição. O problema é minúsculo (dezenas de peças,
# poucas mesas) e converge em milissegundos; o teto é só rede de segurança.
SEGUNDOS_PADRAO = 5.0


@dataclass
class Particao:
    """Resultado do CP-SAT: as unidades de cada mesa e por que parou."""

    mesas: list[list[Unidade]]
    status: str
    areas: list[float] = field(default_factory=list)


def capacidade_cm2(largura_cm: float, limite_cm: float, densidade_alvo: float) -> float:
    """Área que uma mesa aguenta antes de o comprimento estourar o limite."""
    return max(0.0, largura_cm * limite_cm * densidade_alvo)


def k_minimo(area: float, capacidade: float, minimo: int = 1) -> int:
    """Menor número de mesas em que a área cabe na capacidade."""
    if capacidade <= 0:
        return minimo
    return max(minimo, math.ceil(area / capacidade))


def dividir(
    unidades: list[Unidade],
    mesas: list[int],
    capacidades: list[float],
    *,
    proibidas: set[tuple[int, int]] | None = None,
    segundos: float = SEGUNDOS_PADRAO,
    seed: int = 0,
    workers: int = 1,
) -> Particao | None:
    """Reparte `unidades` entre as mesas `mesas` (índices), respeitando a
    área restante de cada uma.

    mesas       índices das mesas AINDA ABERTAS (as já fechadas não recebem
                mais nada, então ficam fora e a capacidade delas é 0)
    capacidades área que sobra em cada mesa aberta, na mesma ordem
    proibidas   pares (índice da unidade, índice da mesa) que não podem
                acontece — é a "restrição extra" do ciclo de ajuste

    Devolve None se não achou solução (sem espaço, ou peça maior que a mesa):
    quem chama trata como "sobe o K".
    """
    if not mesas or not unidades:
        return Particao(mesas=[[] for _ in mesas], status="VAZIO")

    # CP-SAT é inteiro: área em cm² arredondada para cima, para nunca
    # "caber" uma peça que não cabe.
    areas = [max(1, int(u.area_cm2 + 0.5)) for u in unidades]
    cargas = [max(0, int(c + 0.5)) for c in capacidades]
    proibidas = proibidas or set()

    modelo = cp_model.CpModel()
    x = [[modelo.NewBoolVar(f"x{i}_{j}") for j in range(len(mesas))] for i in range(len(unidades))]

    for i in range(len(unidades)):
        modelo.AddExactlyOne(x[i])
        for j, t in enumerate(mesas):
            if cargas[j] <= 0 or (unidades[i].indice, t) in proibidas:
                modelo.Add(x[i][j] == 0)

    for j in range(len(mesas)):
        modelo.Add(sum(areas[i] * x[i][j] for i in range(len(unidades))) <= cargas[j])

    # Objetivo: minimizar a mesa mais cheia (makespan). Sem objetivo o solver
    # devolve a primeira solução factível — na prática uma partição gulosa que
    # empilhava 16–18 mil cm² numa mesa (que nunca cabe no limite de comprimento)
    # e deixava outras quase vazias, e o ajuste/proibidas não desfazia isso.
    # Minimizar o máximo equilibra as mesas por área, e aí o encaixe fecha cada
    # uma dentro do limite.
    maximo = modelo.NewIntVar(0, max(cargas) if cargas else 0, "maxcarga")
    for j in range(len(mesas)):
        modelo.Add(sum(areas[i] * x[i][j] for i in range(len(unidades))) <= maximo)
    modelo.Minimize(maximo)

    # par: as duas metades na mesma mesa
    por_par: dict[int, list[int]] = {}
    for i, u in enumerate(unidades):
        if u.par is not None:
            por_par.setdefault(u.par, []).append(i)
    for metade in por_par.values():
        for a, b in zip(metade, metade[1:]):
            for j in range(len(mesas)):
                modelo.Add(x[a][j] == x[b][j])

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.1, float(segundos))
    solver.parameters.num_search_workers = max(1, int(workers))
    solver.parameters.random_seed = int(seed)
    status = solver.Solve(modelo)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    resultado: list[list[Unidade]] = [[] for _ in mesas]
    cargas_reais = [0.0] * len(mesas)
    for i, u in enumerate(unidades):
        for j in range(len(mesas)):
            if solver.Value(x[i][j]):
                resultado[j].append(u)
                cargas_reais[j] += u.area_cm2
    return Particao(mesas=resultado, status=solver.StatusName(status), areas=cargas_reais)
