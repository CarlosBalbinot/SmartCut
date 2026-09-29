"""planejador.py — OR-Tools CP-SAT escolhe o LOTE que tenta entrar numa mesa.

O spyrrow resolve strip packing (minimizar o comprimento de UMA faixa, sem
teto). Quem decide o que vai para cada mesa é o motor (motor.py), enchendo
uma mesa por vez; aqui fica a parte combinatória desse enchimento:

    mochila(blocos, livre_cm2) → o subconjunto de blocos de MAIOR área que
                                 cabe na área livre da mesa

Um bloco é o que não pode se separar: uma peça simples, ou as duas metades de
um par (que precisam cair na mesma mesa, como no v1). A área livre é
`capacidade_cm2(...) − área já posta`; `densidade` é o quanto se espera
aproveitar de uma mesa. A mochila só PROPÕE: quem decide se o lote coube é o
spyrrow (motor.py corta o que passar do limite e tenta de novo).

Histórico (M1): a primeira versão do v2 usava o CP-SAT para dividir todas as
peças em K mesas equilibradas por área (makespan). Equilibrar espalha as
peças pequenas por todas as mesas; com moldes de ~99 cm numa mesa de 150 cada
mesa ficava com uma fileira de grandes + uma faixa de pequenas, e o PRETO
parou em 6,04 m. O M1-B enche mesa por mesa (grandes primeiro, pequenas nas
folgas) e fica em ~5,7 m — ver experimentos/nesting/resultados/RELATORIO_M1B.md.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from services.nesting_v2.geometria import Unidade

# Segundos de CP-SAT por mochila. São dezenas de blocos: converge em
# milissegundos; o teto é só rede de segurança.
SEGUNDOS_PADRAO = 2.0


def capacidade_cm2(largura_cm: float, limite_cm: float, densidade: float) -> float:
    """Área que uma mesa aguenta antes de o comprimento estourar o limite."""
    return max(0.0, largura_cm * limite_cm * densidade)


def area_bloco(bloco: list[Unidade]) -> float:
    return sum(u.area_cm2 for u in bloco)


def blocos(unidades: list[Unidade]) -> list[list[Unidade]]:
    """Agrupa as unidades em blocos inseparáveis (par = 2 unidades), do maior
    para o menor em área. Empate: ordem de entrada (estável)."""
    grupos: dict[tuple, list[Unidade]] = {}
    for u in unidades:
        chave = ("par", u.par) if u.par is not None else ("un", u.indice)
        grupos.setdefault(chave, []).append(u)
    return sorted(grupos.values(), key=lambda b: -area_bloco(b))


def mochila(
    candidatos: list[list[Unidade]],
    livre_cm2: float,
    *,
    segundos: float = SEGUNDOS_PADRAO,
    seed: int = 0,
) -> list[list[Unidade]]:
    """Blocos de maior área total que somam <= `livre_cm2`.

    Devolve [] se nenhum bloco cabe. Com 1 worker e a mesma seed o CP-SAT é
    determinístico.
    """
    livre = int(livre_cm2)
    cabem = [b for b in candidatos if 0 < area_bloco(b) <= livre]
    if not cabem:
        return []
    # CP-SAT é inteiro: área arredondada para cima, para nunca "caber" um
    # bloco que não cabe.
    areas = [int(area_bloco(b)) + 1 for b in cabem]

    modelo = cp_model.CpModel()
    x = [modelo.NewBoolVar(f"b{i}") for i in range(len(cabem))]
    modelo.Add(sum(a * v for a, v in zip(areas, x)) <= livre)
    modelo.Maximize(sum(a * v for a, v in zip(areas, x)))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.1, float(segundos))
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = int(seed)
    status = solver.Solve(modelo)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return []
    return [b for b, v in zip(cabem, x) if solver.Value(v)]
