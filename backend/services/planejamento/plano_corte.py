"""plano_corte.py — o plano de corte de um PRODUTO: quais riscos desenhar e
quantas camadas de cada COR vão em cada risco (enfesto multicor).

Puro: nada de banco, nada de motor. O comprimento de cada risco vem do
estimador (área / largura / aproveitamento + ponta de mesa); quem roda o
motor depois é o nesting_service (_gerar_plano_corte).

O problema
----------
Um produto tem uma grade por cor (PRETO: P1 M2 G2 · MARROM: M2 G1 …). Um
RISCO é um desenho com k conjuntos de cada tamanho, numa largura; estendido
com L camadas de uma cor, ele corta L × k peças de cada tamanho daquela cor.
Várias cores podem ir no mesmo enfesto do risco (PRETO 7 camadas + MARROM 7
camadas), e um risco pode ter mais de um enfesto quando as camadas passam do
teto.

Regras
------
  * nenhuma cor falta: cada (cor, tamanho) sai com >= o pedido;
  * SOBRA só quando é inevitável: o plano tem sempre a MENOR sobra possível
    (zero no enfesto simples; no duplo com peça `par`, a que as camadas pares
    obrigam). A tolerância de tecido escolhe entre planos com essa sobra —
    nunca se aceita peça a mais para economizar desenho;
  * teto: a SOMA das camadas de todas as cores de um enfesto <= max_camadas
    do modelo de tecido;
  * enfesto duplo com peça `par`: camadas PARES por cor (cada par de camadas
    corta a direita e a esquerda) — e o teto vira o par abaixo;
  * largura: empilham-se cores do MESMO modelo de tecido com diferença de
    largura de até LARGURA_MAX_DIFERENCA_CM (agrupar_cores). Cada risco é
    desenhado numa das larguras do grupo e só recebe cores com largura maior
    ou igual — a cor mais larga cortada num risco estreito gasta mais
    comprimento, e isso entra no consumo: a tolerância decide se empilhar
    compensa ou se é melhor separar.

Riscos candidatos (até MAX_MESAS_RISCO mesas cada)
--------------------------------------------------
Pelos divisores da grade de cada cor: para k = 1..teto, a grade dividida por
k (arredondada para cima e para baixo — o resto vai para outro risco). Mais os
riscos do plano por cor de hoje (plano_enfesto, SEM_SOBRA), para que o plano
atual seja sempre uma solução possível, e um conjunto de cada tamanho
(garante que sempre existe solução). Cada vetor entra em cada largura do grupo.

Critério (CP-SAT, em etapas, cada uma fixando a anterior)
---------------------------------------------------------
  0. a menor sobra possível (fica travada daqui em diante);
  1. o menor consumo de tecido (comprimento × camadas, todos os riscos);
  2. aceitando até `tolerancia_pct` a mais que esse mínimo (Configurações >
     Produção, padrão 2%): menos mesas; depois menos desenhos; por fim o
     menor consumo que sobrar.
O motivo em texto compara com o plano de menor consumo.

Determinístico: 1 worker, semente fixa e tempo determinístico — o mesmo
pedido dá o mesmo plano em qualquer máquina.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from services.plano_enfesto import planejar
from services.planejamento import estimador

TOLERANCIA_PADRAO_PCT = 2.0
LARGURA_MAX_DIFERENCA_CM = 5.0
TEMPO_PADRAO_S = 10.0
# Risco candidato com mais mesas que isso fica de fora. Sem teto, o menor
# consumo "teórico" é um risco só com a grade inteira em 2 camadas (91 mesas
# na OC-0004) — impossível de estender e caro demais para o motor. O maior
# risco das OCs de hoje tem 10 mesas.
MAX_MESAS_RISCO = 12


# ── Entrada ──────────────────────────────────────────────────────────────────


@dataclass
class CorGrade:
    """Uma cor do produto: a grade pedida e o tecido dela. `cor` é a chave
    (única no grupo); `nome` o que se mostra (vazio = a própria chave)."""

    cor: str
    grade: dict[str, int]
    modelo_tecido: str = ""
    largura_cm: float = 0.0
    max_camadas: int = 15
    nome: str = ""


def agrupar_cores(
    cores: Iterable[CorGrade], diferenca_max_cm: float = LARGURA_MAX_DIFERENCA_CM
) -> list[list[CorGrade]]:
    """Grupos que podem dividir o mesmo enfesto: mesmo modelo de tecido e
    larguras dentro de `diferenca_max_cm` (do mais estreito ao mais largo do
    grupo). A ordem das cores dentro do grupo é a da entrada."""
    cores = list(cores)
    ordem = {id(c): i for i, c in enumerate(cores)}
    por_modelo: dict[str, list[CorGrade]] = {}
    for c in cores:
        por_modelo.setdefault(c.modelo_tecido, []).append(c)
    grupos: list[list[CorGrade]] = []
    for lista in por_modelo.values():
        atual: list[CorGrade] = []
        for c in sorted(lista, key=lambda c: c.largura_cm):
            if atual and c.largura_cm - atual[0].largura_cm > diferenca_max_cm + 1e-9:
                grupos.append(atual)
                atual = []
            atual.append(c)
        if atual:
            grupos.append(atual)
    for g in grupos:
        g.sort(key=lambda c: ordem[id(c)])
    grupos.sort(key=lambda g: ordem[id(g[0])])
    return grupos


# ── Saída ────────────────────────────────────────────────────────────────────


@dataclass
class RiscoPlano:
    """Um desenho do plano e como ele é estendido."""

    conjuntos: dict[str, int]
    largura_cm: float
    comprimento_cm: float
    mesas_por_enfesto: int
    camadas_por_cor: dict[str, int]
    # Cada enfesto: {cor: camadas}; soma <= teto.
    enfestos: list[dict[str, int]] = field(default_factory=list)

    @property
    def camadas(self) -> int:
        return sum(self.camadas_por_cor.values())

    @property
    def metros(self) -> float:
        return self.comprimento_cm * self.camadas / 100

    @property
    def mesas(self) -> int:
        return self.mesas_por_enfesto * len(self.enfestos)

    def rotulo(self) -> str:
        return " ".join(f"{t}{n}" for t, n in self.conjuntos.items() if n)

    def json(self) -> dict:
        return {
            "conjuntos": self.conjuntos,
            "rotulo": self.rotulo(),
            "largura_cm": self.largura_cm,
            "comprimento_cm": round(self.comprimento_cm, 1),
            "mesas_por_enfesto": self.mesas_por_enfesto,
            "camadas_por_cor": self.camadas_por_cor,
            "enfestos": self.enfestos,
            "metros": round(self.metros, 2),
            "mesas": self.mesas,
        }


@dataclass
class PlanoCorte:
    riscos: list[RiscoPlano]
    sobra_por_cor: dict[str, dict[str, int]]
    teto_camadas: int
    camadas_pares: bool
    tolerancia_pct: float
    # Referência: o plano de MENOR consumo (com a mesma sobra mínima).
    metros_minimo: float = 0.0
    mesas_minimo: int = 0
    desenhos_minimo: int = 0
    otimo: bool = True
    motivo: str = ""

    @property
    def metros(self) -> float:
        return sum(r.metros for r in self.riscos)

    @property
    def mesas(self) -> int:
        return sum(r.mesas for r in self.riscos)

    @property
    def desenhos(self) -> int:
        return len(self.riscos)

    @property
    def camadas(self) -> int:
        return sum(r.camadas for r in self.riscos)

    @property
    def sobra_total(self) -> int:
        return sum(sum(v.values()) for v in self.sobra_por_cor.values())

    def cortado(self) -> dict[str, dict[str, int]]:
        """Peças cortadas por cor e tamanho."""
        saida: dict[str, dict[str, int]] = {}
        for r in self.riscos:
            for cor, cam in r.camadas_por_cor.items():
                alvo = saida.setdefault(cor, {})
                for t, n in r.conjuntos.items():
                    alvo[t] = alvo.get(t, 0) + cam * n
        return saida

    def json(self) -> dict:
        return {
            "riscos": [r.json() for r in self.riscos],
            "metros": round(self.metros, 2),
            "mesas": self.mesas,
            "desenhos": self.desenhos,
            "sobra_por_cor": self.sobra_por_cor,
            "sobra_total": self.sobra_total,
            "teto_camadas": self.teto_camadas,
            "camadas_pares": self.camadas_pares,
            "tolerancia_pct": self.tolerancia_pct,
            "metros_minimo": round(self.metros_minimo, 2),
            "mesas_minimo": self.mesas_minimo,
            "desenhos_minimo": self.desenhos_minimo,
            "otimo": self.otimo,
            "motivo": self.motivo,
        }


# ── Candidatos ───────────────────────────────────────────────────────────────


def _teto(max_camadas: int, pares: bool) -> int:
    teto = max(1, int(max_camadas))
    if pares:
        if teto < 2:
            raise ValueError("enfesto duplo com peça em par precisa de pelo menos 2 camadas no tecido")
        teto -= teto % 2
    return teto


def _chave(conjuntos: Mapping[str, int], tamanhos: list[str]) -> tuple[int, ...]:
    return tuple(int(conjuntos.get(t, 0)) for t in tamanhos)


def candidatos(
    cores: list[CorGrade], tamanhos: list[str], teto: int, pares: bool
) -> tuple[list[tuple[int, ...]], set[tuple[int, ...]]]:
    """(riscos candidatos, os que são do plano por cor de hoje). Cada risco é
    o vetor de conjuntos na ordem de `tamanhos`; sem repetição, na ordem em
    que foram achados."""
    vistos: dict[tuple[int, ...], None] = {}
    de_hoje: set[tuple[int, ...]] = set()

    def _add(v: tuple[int, ...]) -> None:
        if any(v):
            vistos.setdefault(v, None)

    for c in cores:
        grade = [int(c.grade.get(t, 0)) for t in tamanhos]
        maior = max(grade, default=0)
        for k in range(1, min(teto, maior) + 1):
            _add(tuple(math.ceil(q / k) for q in grade))
            _add(tuple(q // k for q in grade))
        # O plano por cor de hoje também é candidato: o plano atual é sempre
        # uma solução possível do modelo.
        plano = planejar({t: q for t, q in zip(tamanhos, grade) if q}, teto, "SEM_SOBRA", camadas_pares=pares)
        for e in plano["enfestos"]:
            v = _chave(e["conjuntos_por_tamanho"], tamanhos)
            _add(v)
            de_hoje.add(v)
    for i in range(len(tamanhos)):
        _add(tuple(1 if j == i else 0 for j in range(len(tamanhos))))
    return list(vistos), de_hoje


# ── O modelo ─────────────────────────────────────────────────────────────────


def _enfestos(camadas_por_cor: dict[str, int], n: int, teto: int) -> list[dict[str, int]]:
    """Distribui as camadas das cores em `n` enfestos de até `teto`, uma cor
    depois da outra (a cor só se divide quando não cabe no que sobrou). Com
    teto par e camadas pares, cada pedaço continua par."""
    enfestos: list[dict[str, int]] = [{} for _ in range(max(1, n))]
    i, livre = 0, teto
    for cor, cam in camadas_por_cor.items():
        while cam > 0:
            if livre == 0:
                i, livre = i + 1, teto
                if i >= len(enfestos):
                    enfestos.append({})
            parte = min(cam, livre)
            enfestos[i][cor] = enfestos[i].get(cor, 0) + parte
            cam -= parte
            livre -= parte
    return [e for e in enfestos if e]


def planejar_corte(
    cores: list[CorGrade],
    area_por_tamanho: Mapping[str, float],
    *,
    limite_mesa_cm: float,
    camadas_pares: bool = False,
    tolerancia_pct: float = TOLERANCIA_PADRAO_PCT,
    tempo_s: float = TEMPO_PADRAO_S,
) -> PlanoCorte:
    """Plano de corte de UM grupo de cores que podem dividir o enfesto (ver
    agrupar_cores): mesmo modelo de tecido, larguras dentro de
    LARGURA_MAX_DIFERENCA_CM. O teto é o menor max_camadas do grupo.

    area_por_tamanho: cm² de um CONJUNTO do tamanho (todas as peças físicas
    do produto naquele tamanho — `par` conta 2).
    camadas_pares: enfesto duplo com peça `par`."""
    cores = [c for c in cores if any(q > 0 for q in c.grade.values())]
    if not cores:
        raise ValueError("nenhuma cor com quantidade")
    if len({c.cor for c in cores}) != len(cores):
        raise ValueError("cor repetida no grupo")
    tamanhos = [t for t in area_por_tamanho if any(c.grade.get(t, 0) > 0 for c in cores)]
    faltando = {t for c in cores for t, q in c.grade.items() if q > 0 and t not in area_por_tamanho}
    if faltando:
        raise ValueError(f"sem área para o(s) tamanho(s): {', '.join(sorted(faltando))}")
    teto = _teto(min(c.max_camadas for c in cores), camadas_pares)
    passo = 2 if camadas_pares else 1
    larguras = sorted({float(c.largura_cm) for c in cores})
    largura_cor = {c.cor: float(c.largura_cm) for c in cores}

    # Cada vetor em cada largura do grupo: (vetor, largura).
    vetores, de_hoje = candidatos(cores, tamanhos, teto, camadas_pares)
    pool: list[tuple[tuple[int, ...], float]] = []
    comp: list[float] = []
    mesas_r: list[int] = []
    for w in larguras:
        for v in vetores:
            c_cm, q = estimador.estimar(dict(zip(tamanhos, v)), area_por_tamanho, w, limite_mesa_cm)
            # Risco longo demais não entra (mesa e motor), salvo os do plano
            # de hoje — que precisa continuar sendo uma solução possível.
            if q <= MAX_MESAS_RISCO or v in de_hoje:
                pool.append((v, w))
                comp.append(c_cm)
                mesas_r.append(q)
    comp_mm = [max(1, round(c * 10)) for c in comp]
    grade = {c.cor: [int(c.grade.get(t, 0)) for t in tamanhos] for c in cores}

    R, C = range(len(pool)), [c.cor for c in cores]
    # A cor só entra em risco de largura <= a dela.
    pode = {(r, cor) for r in R for cor in C if pool[r][1] <= largura_cor[cor] + 1e-9}
    # Camadas de cada cor em cada risco (em passos de 2 no duplo com par).
    ub = {cor: math.ceil(max(grade[cor]) / passo) for cor in C}
    n_max = math.ceil(sum(ub.values()) * passo / teto)

    def _montar() -> tuple[cp_model.CpModel, dict]:
        """O modelo do zero (cada etapa abaixo usa um modelo próprio: o
        CP-SAT não retira restrição de um modelo já montado)."""
        m = cp_model.CpModel()
        y = {(r, cor): m.NewIntVar(0, ub[cor], f"y{r}_{cor}") for r, cor in pode}
        cam = {k: passo * v for k, v in y.items()}
        n = {r: m.NewIntVar(0, n_max, f"n{r}") for r in R}
        u = {r: m.NewBoolVar(f"u{r}") for r in R}
        for r in R:
            soma = sum(cam[r, cor] for cor in C if (r, cor) in cam)
            m.Add(soma <= teto * n[r])  # teto: soma das cores por enfesto
            m.Add(n[r] <= n_max * u[r])
            m.Add(soma >= u[r])
            for cor in C:
                if (r, cor) in y:
                    m.Add(y[r, cor] <= ub[cor] * u[r])
        sobra_termos = []
        for cor in C:
            for j in range(len(tamanhos)):
                cortado = sum(pool[r][0][j] * cam[r, cor] for r in R if pool[r][0][j] and (r, cor) in cam)
                m.Add(cortado >= grade[cor][j])  # nenhuma cor falta
                sobra_termos.append(cortado - grade[cor][j])
        h = {
            "y": y,
            "n": n,
            "u": u,
            "cam": cam,
            "tecido": sum(comp_mm[r] * v for (r, _cor), v in cam.items()),
            "mesas": sum(mesas_r[r] * n[r] for r in R),
            "desenhos": sum(u.values()),
            "sobra": sum(sobra_termos),
        }
        return m, h

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 0
    # Tempo DETERMINÍSTICO (unidade do CP-SAT, ~1 s numa máquina comum): o
    # mesmo pedido dá o mesmo plano em qualquer máquina. O relógio de verdade
    # fica só como teto de segurança.
    solver.parameters.max_deterministic_time = max(0.5, tempo_s / 7)
    solver.parameters.max_time_in_seconds = max(1.0, tempo_s)
    otimo = True
    anterior: dict = {}

    def _fase(m: cp_model.CpModel, h: dict, objetivo) -> int:
        nonlocal otimo, anterior
        m.ClearHints()
        for (tipo, k), valor in anterior.items():
            m.AddHint(h[tipo][k], valor)
        m.Minimize(objetivo)
        status = solver.Solve(m)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError("plano de corte sem solução (verifique o teto de camadas)")
        otimo = otimo and status == cp_model.OPTIMAL
        # A solução desta etapa é a dica da próxima (e continua válida nela).
        anterior = {(tipo, k): solver.Value(v) for tipo in ("y", "n", "u") for k, v in h[tipo].items()}
        return round(solver.ObjectiveValue())

    # 0 — a menor sobra possível; fica travada em todas as etapas.
    m, h = _montar()
    sobra_min = _fase(m, h, h["sobra"])
    # 1 — o menor consumo com essa sobra.
    m, h = _montar()
    m.Add(h["sobra"] <= sobra_min)
    minimo = _fase(m, h, h["tecido"])
    # Referência para o motivo: o plano de menor consumo com menos mesas (e,
    # empatando, menos desenhos).
    m, h = _montar()
    m.Add(h["sobra"] <= sobra_min)
    m.Add(h["tecido"] <= minimo)
    _fase(m, h, h["mesas"] * (len(pool) + 1) + h["desenhos"])
    ref_mesas, ref_desenhos = solver.Value(h["mesas"]), solver.Value(h["desenhos"])
    # 2 — dentro da tolerância: menos mesas, menos desenhos e, por fim, o
    # menor consumo que sobrar.
    m, h = _montar()
    m.Add(h["sobra"] <= sobra_min)
    m.Add(h["tecido"] <= math.floor(minimo * (1 + tolerancia_pct / 100)))
    for criterio in ("mesas", "desenhos"):
        m.Add(h[criterio] <= _fase(m, h, h[criterio]))
    _fase(m, h, h["tecido"])
    n, u, cam = h["n"], h["u"], h["cam"]

    riscos: list[RiscoPlano] = []
    for r in R:
        if not solver.Value(u[r]):
            continue
        camadas_cor = {cor: solver.Value(cam[r, cor]) for cor in C if (r, cor) in cam and solver.Value(cam[r, cor])}
        riscos.append(
            RiscoPlano(
                conjuntos={t: q for t, q in zip(tamanhos, pool[r][0]) if q},
                largura_cm=pool[r][1],
                comprimento_cm=comp[r],
                mesas_por_enfesto=mesas_r[r],
                camadas_por_cor=camadas_cor,
                enfestos=_enfestos(camadas_cor, solver.Value(n[r]), teto),
            )
        )
    # Mais camadas primeiro: é o risco principal do plano.
    riscos.sort(key=lambda r: (-r.camadas, -sum(r.conjuntos.values()), r.largura_cm))
    plano = PlanoCorte(
        riscos=riscos,
        sobra_por_cor={},
        teto_camadas=teto,
        camadas_pares=camadas_pares,
        tolerancia_pct=tolerancia_pct,
        metros_minimo=minimo / 1000,
        mesas_minimo=ref_mesas,
        desenhos_minimo=ref_desenhos,
        otimo=otimo,
    )
    cortado = plano.cortado()
    sobra = {
        cor: {
            t: cortado.get(cor, {}).get(t, 0) - grade[cor][j]
            for j, t in enumerate(tamanhos)
            if cortado.get(cor, {}).get(t, 0) > grade[cor][j]
        }
        for cor in C
    }
    plano.sobra_por_cor = {k: v for k, v in sobra.items() if v}
    plano.motivo = _motivo(plano)
    return plano


def _m(v: float) -> str:
    return f"{v:.2f} m".replace(".", ",")


def _pct(v: float) -> str:
    return f"{v:.1f}%".replace(".", ",")


def _plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


def _motivo(p: PlanoCorte) -> str:
    base = f"{_plural(p.desenhos, 'desenho', 'desenhos')}, {_plural(p.mesas, 'mesa', 'mesas')}, {_m(p.metros)}"
    if p.sobra_total:
        base += f", sobra de {_plural(p.sobra_total, 'peça', 'peças')} (inevitável: camadas pares)"
    extra = (p.metros - p.metros_minimo) / p.metros_minimo * 100 if p.metros_minimo else 0.0
    if (p.mesas, p.desenhos) == (p.mesas_minimo, p.desenhos_minimo) or extra < 0.05:
        return f"{base}: o menor consumo."
    return (
        f"{base}: +{_pct(extra)} de tecido sobre o menor consumo ({_m(p.metros_minimo)}, "
        f"{_plural(p.desenhos_minimo, 'desenho', 'desenhos')}, {_plural(p.mesas_minimo, 'mesa', 'mesas')}), "
        f"dentro da tolerância de {p.tolerancia_pct:g}% para simplificar o corte."
    )


# ── Comparação: o plano por cor de hoje ──────────────────────────────────────


def plano_por_cor(
    cores: list[CorGrade],
    area_por_tamanho: Mapping[str, float],
    *,
    limite_mesa_cm: float,
    camadas_pares: bool = False,
) -> PlanoCorte:
    """O que o sistema faz hoje (plano_enfesto SEM_SOBRA, uma cor por vez, na
    largura da própria cor), medido com o MESMO estimador — a base da
    comparação."""
    riscos: list[RiscoPlano] = []
    sobra: dict[str, dict[str, int]] = {}
    for c in cores:
        teto = _teto(c.max_camadas, camadas_pares)
        plano = planejar({t: q for t, q in c.grade.items() if q}, teto, "SEM_SOBRA", camadas_pares=camadas_pares)
        for e in plano["enfestos"]:
            conj = {t: e["conjuntos_por_tamanho"][t] for t in area_por_tamanho if t in e["conjuntos_por_tamanho"]}
            comp, mesas = estimador.estimar(conj, area_por_tamanho, c.largura_cm, limite_mesa_cm)
            riscos.append(
                RiscoPlano(
                    conjuntos=conj,
                    largura_cm=float(c.largura_cm),
                    comprimento_cm=comp,
                    mesas_por_enfesto=mesas,
                    camadas_por_cor={c.cor: e["camadas"]},
                    enfestos=[{c.cor: e["camadas"]}],
                )
            )
        s = {t: v for t, v in plano["sobra_por_tamanho"].items() if v}
        if s:
            sobra[c.cor] = s
    return PlanoCorte(
        riscos=riscos,
        sobra_por_cor=sobra,
        teto_camadas=min(c.max_camadas for c in cores),
        camadas_pares=camadas_pares,
        tolerancia_pct=0.0,
        motivo="plano por cor (hoje)",
    )
