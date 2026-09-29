"""motor.py — o v2 de ponta a ponta: preparar → encher mesa por mesa → polir.

`gerar(pecas, largura_cm, comprimento_max_cm, camadas)` devolve um
`Resultado`: as mesas do enfesto (cada uma no formato de mapa_json do v1) e o
resumo do enfesto (grade por tamanho, metros, tempo, pico de memória).

Tabela por mesa × resumo do enfesto
-----------------------------------
Cada mesa lista os MOLDES que corta (FRENTE G x1, COSTAS M x2 — `pecas_parte`
no mapa_json). A grade por tamanho (P1 M2 G3) é do enfesto e sai só em
`Resultado.resumo_enfesto()`. O v1 repetia a grade do enfesto em todas as
partes (nesting_service: `extras["pecas_por_tamanho"]` copiado em cada parte),
e o relatório de produção somava o mesmo enfesto uma vez por parte.

Como as mesas são montadas (M1-B)
---------------------------------
O spyrrow minimiza o comprimento de uma faixa mas não tem teto, então a
divisão em mesas é feita aqui, UMA MESA POR VEZ, com o spyrrow como oráculo
("coube em <= limite?"):

  1. GRANDES — peças que não cabem duas vezes no comprimento da mesa
     (altura > limite/2: FRENTE/COSTAS de ~99 cm numa mesa de 150). Elas
     definem quantas mesas existem. Enche-se a mesa com a maior peça que
     ainda cabe, testando no spyrrow; uma forma que não coube não é testada
     de novo nesta mesa. Quando nada mais cabe, abre-se a próxima.
  2. PEQUENAS — vão para as folgas, começando pela mesa mais curta. O
     CP-SAT (planejador.mochila) propõe o lote de maior área que cabe na área
     livre; o spyrrow encaixa mesa + lote; o que passar do limite é cortado
     (a faixa até o limite continua válida) e volta para a fila. Se nenhuma
     mesa aceita mais nada, abre-se uma mesa nova do mesmo jeito.
  3. POLIMENTO — cada mesa é reencaixada com mais tempo; fica a mais curta.

Por que não equilibrar: a versão M1 dividia por CP-SAT em K mesas de área
parecida, o que espalhava as peças pequenas e deixava cada mesa com uma
fileira de grandes + uma faixa de pequenas (PRETO 150: 6,04 m). Enchendo
mesa por mesa as pequenas fecham os buracos das mesas mais curtas
(PRETO 150: ~5,7 m).

Memória e tempo
---------------
  * spyrrow com no máximo encaixador.MAX_WORKERS threads e UM por vez no
    processo (lock em encaixador.py) — nunca dois motores em paralelo;
  * cada chamada tem teto de tempo (`segundos_mesa`, `segundos_polimento`);
    passado `tempo_max_s` o resto roda no piso de 1 s e o polimento é pulado;
  * o pico de memória do processo durante a geração volta em
    `Resultado.pico_memoria_mb` (memoria.MedidorPico).

Progresso e cancelamento
------------------------
`ao_progresso(fase, mesa, total_mesas, aproveitamento)` é chamado antes de
cada chamada do spyrrow (fases "grandes", "pequenas", "polimento"). Quem roda
em segundo plano (services/nesting_jobs.py) usa para mostrar a mesa atual e,
levantando uma exceção dentro dele, cancelar entre uma mesa/fase e outra — a
geração só devolve algo no fim, então cancelar não deixa nada pela metade.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from services.nesting_v2 import planejador
from services.nesting_v2.encaixador import (
    MAX_WORKERS,
    ErroEncaixe,
    Faixa,
    Posicao,
    comprimento_de,
    desloca,
    encaixar,
)
from services.nesting_v2.geometria import (
    EPS_CM,
    Peca,
    Unidade,
    area_total,
    bbox,
    grade_por_tamanho,
    por_molde,
    preparar,
    rotacionar,
)
from services.nesting_v2.memoria import MedidorPico

# Fração da mesa que a mochila tenta preencher. Otimista de propósito: o
# spyrrow decide o que coube e o excedente volta para a fila.
DENSIDADE_ALVO = 0.90

# Tentativas de um lote numa mesa antes de desistir dela (cada uma encolhe o
# lote para o que coube na anterior).
TENTATIVAS_LOTE = 3

# Orçamentos padrão do spyrrow, em segundos por chamada.
SEGUNDOS_MESA = 2.0  # teste "coube?" durante o enchimento
SEGUNDOS_POLIMENTO = 6.0  # reencaixe final de cada mesa
SEGUNDOS_FAIXA = 30.0  # sem limite de mesa: uma faixa só
TEMPO_MAX_S = 600.0  # teto brando da geração inteira

# Piso de uma chamada: o spyrrow trabalha em segundos inteiros.
SEGUNDO_PISO = 1.0

# (fase, mesa, total_mesas, aproveitamento da última faixa que coube)
Progresso = Callable[[str, int, int, float | None], None]


@dataclass
class Mesa:
    """Uma mesa (risco) do enfesto, pronta para virar Encaixe."""

    indice: int
    comprimento_cm: float
    aproveitamento: float
    pecas: list[dict] = field(default_factory=list)
    unidades: list[Unidade] = field(default_factory=list)
    posicoes: list[Posicao] = field(default_factory=list)

    def moldes(self, camadas: int = 1) -> list[dict]:
        """O que esta mesa corta, por molde (ver geometria.por_molde)."""
        return por_molde(self.unidades, camadas)

    def mapa_json(self, *, largura_cm: float, camadas: int = 1, **contexto: Any) -> dict:
        """mapa_json no formato do v1 (nesting_service._montar_encaixe).

        `pecas_parte` é a tabela DA MESA, por molde. Não há
        `pecas_por_tamanho` aqui: a grade é do enfesto e sai no
        `Resultado.resumo_enfesto()`. `contexto` entra por último, como os
        `extras` do v1 (lote_id, tecido_id, total_partes...). `parte` (o texto
        "2/5") só sai quando há mais de uma mesa, como no v1.
        """
        mapa: dict[str, Any] = {
            "largura_cm": largura_cm,
            "comprimento_cm": round(self.comprimento_cm, 3),
            "num_camadas": camadas,
            "efficiency": round(self.aproveitamento, 4),
            "placements": self.pecas,
            "parts_count": len(self.pecas),
            "pecas_parte": self.moldes(camadas),
            "parte_numero": self.indice,
            **contexto,
        }
        if int(contexto.get("total_partes") or 1) > 1:
            mapa["parte"] = f"{self.indice}/{int(contexto['total_partes'])}"
        return mapa


@dataclass
class Resultado:
    """Mesas do enfesto + o que se mediu para gerá-las."""

    mesas: list[Mesa]
    largura_cm: float
    camadas: int
    segundos: float = 0.0
    pico_memoria_mb: float | None = None
    chamadas_spyrrow: int = 0

    @property
    def comprimento_total_cm(self) -> float:
        return sum(m.comprimento_cm for m in self.mesas)

    @property
    def aproveitamento_medio(self) -> float:
        total = self.comprimento_total_cm
        cortada = sum(u.area_cm2 for m in self.mesas for u in m.unidades)
        return cortada / (self.largura_cm * total) if total > EPS_CM else 0.0

    @property
    def pior_mesa(self) -> float:
        return min((m.aproveitamento for m in self.mesas), default=0.0)

    def resumo_enfesto(self) -> dict:
        """Resumo do ENFESTO: a grade por tamanho fica aqui, uma vez só."""
        return {
            "pecas_por_tamanho": grade_por_tamanho([u for m in self.mesas for u in m.unidades], self.camadas),
            "total_partes": len(self.mesas),
            "comprimento_total_cm": round(self.comprimento_total_cm, 3),
            "aproveitamento_medio": round(self.aproveitamento_medio, 4),
            "pior_mesa": round(self.pior_mesa, 4),
            "segundos": round(self.segundos, 2),
            "pico_memoria_mb": round(self.pico_memoria_mb, 1) if self.pico_memoria_mb is not None else None,
        }

    def mapas_json(self, **contexto: Any) -> list[dict]:
        """Um mapa_json por mesa, já com total_partes."""
        return [
            m.mapa_json(largura_cm=self.largura_cm, camadas=self.camadas, total_partes=len(self.mesas), **contexto)
            for m in self.mesas
        ]


# ── Geração ──────────────────────────────────────────────────────────────────


def gerar(
    pecas: list[Peca],
    largura_cm: float,
    comprimento_max_cm: float | None,
    camadas: int = 1,
    *,
    seed: int = 0,
    workers: int = MAX_WORKERS,
    margem_cm: float = 0.0,
    segundos_mesa: float = SEGUNDOS_MESA,
    segundos_polimento: float = SEGUNDOS_POLIMENTO,
    segundos_faixa: float = SEGUNDOS_FAIXA,
    tempo_max_s: float = TEMPO_MAX_S,
    ao_progresso: Progresso | None = None,
) -> Resultado:
    """Divide as peças do enfesto em mesas de comprimento <= limite.

    largura_cm         largura útil do tecido (eixo x das mesas)
    comprimento_max_cm limite da OC; None = sem limite (uma faixa só)
    camadas            camadas do mesmo risco — não muda o plano, entra no
                       mapa_json e nos totais
    seed               semente do spyrrow e do CP-SAT
    workers            threads do spyrrow (teto: encaixador.MAX_WORKERS)
    margem_cm          separação mínima entre peças (min_items_separation)
    segundos_*         teto de tempo de cada chamada do spyrrow
    tempo_max_s        teto brando da geração: passado dele, as chamadas vão
                       para o piso de 1 s e o polimento é pulado
    ao_progresso       callback antes de cada chamada do spyrrow (ver topo);
                       exceção levantada nele interrompe a geração
    """
    if largura_cm <= 0:
        raise ErroEncaixe(f"Largura do tecido inválida: {largura_cm}")
    if comprimento_max_cm is not None and comprimento_max_cm <= 0:
        raise ErroEncaixe(f"Comprimento máximo inválido: {comprimento_max_cm}")

    inicio = time.perf_counter()
    with MedidorPico() as memoria:
        unidades = preparar(pecas)
        ctx = _Contexto(
            largura_cm=float(largura_cm),
            limite=float(comprimento_max_cm) if comprimento_max_cm is not None else None,
            seed=seed,
            workers=workers,
            margem_cm=margem_cm,
            segundos_mesa=segundos_mesa,
            tempo_max_s=tempo_max_s,
            inicio=inicio,
            ao_progresso=ao_progresso,
        )
        if not unidades:
            mesas: list[Mesa] = []
        elif ctx.limite is None:
            ctx.em("faixa", 1)
            mesas = _finaliza([_Aberta(unidades, ctx.encaixar(unidades, segundos_faixa))])
        else:
            abertas = _encher_grandes(ctx, [u for u in unidades if _altura_min(u) > ctx.limite / 2])
            _encher_pequenas(ctx, abertas, [u for u in unidades if _altura_min(u) <= ctx.limite / 2])
            _polir(ctx, abertas, segundos_polimento)
            mesas = _finaliza(abertas)

    postas = sum(len(m.unidades) for m in mesas)
    if postas != len(unidades):  # pragma: no cover - rede de segurança
        raise ErroEncaixe(f"Encaixe incompleto: {postas} de {len(unidades)} peças")
    return Resultado(
        mesas=mesas,
        largura_cm=float(largura_cm),
        camadas=camadas,
        segundos=time.perf_counter() - inicio,
        pico_memoria_mb=memoria.pico_mb,
        chamadas_spyrrow=ctx.chamadas,
    )


@dataclass
class _Aberta:
    """Mesa em montagem: as unidades e a última faixa que coube."""

    unidades: list[Unidade]
    faixa: Faixa | None = None

    @property
    def comprimento_cm(self) -> float:
        return self.faixa.comprimento_cm if self.faixa else 0.0


@dataclass
class _Contexto:
    largura_cm: float
    limite: float | None
    seed: int
    workers: int
    margem_cm: float
    segundos_mesa: float
    tempo_max_s: float
    inicio: float
    ao_progresso: Progresso | None = None
    chamadas: int = 0
    fase: str = ""
    mesa: int = 0
    total_mesas: int = 0
    aproveitamento: float | None = None

    def em(self, fase: str, mesa: int, total_mesas: int | None = None) -> None:
        """Marca onde a geração está (vai no próximo aviso de progresso)."""
        self.fase, self.mesa = fase, mesa
        self.total_mesas = max(self.total_mesas, mesa, total_mesas or 0)

    @property
    def estourou(self) -> bool:
        return time.perf_counter() - self.inicio > self.tempo_max_s

    def encaixar(self, unidades: list[Unidade], segundos: float | None = None) -> Faixa:
        seg = SEGUNDO_PISO if self.estourou else max(SEGUNDO_PISO, segundos or self.segundos_mesa)
        if self.ao_progresso is not None:
            self.ao_progresso(self.fase, self.mesa, self.total_mesas, self.aproveitamento)
        self.chamadas += 1
        faixa = encaixar(
            unidades,
            self.largura_cm,
            segundos=seg,
            seed=self.seed,
            num_workers=self.workers,
            margem_cm=self.margem_cm,
            nome=f"mesa{self.chamadas}",
        )
        _checar_largura(faixa)
        if self.cabe(faixa):
            self.aproveitamento = faixa.aproveitamento
        return faixa

    def cabe(self, faixa: Faixa) -> bool:
        return self.limite is None or faixa.comprimento_cm <= self.limite + EPS_CM


def _altura_min(u: Unidade) -> float:
    """Menor extensão no comprimento entre as rotações permitidas."""
    alturas = []
    for r in u.rotacoes or (0.0,):
        _, min_y, _, max_y = bbox(rotacionar(u.poligono, r))
        alturas.append(max_y - min_y)
    return min(alturas)


def _sem(unidades: list[Unidade], tirar: list[Unidade]) -> list[Unidade]:
    ids = {u.indice for u in tirar}
    return [u for u in unidades if u.indice not in ids]


def _encher_grandes(ctx: _Contexto, grandes: list[Unidade]) -> list[_Aberta]:
    """Etapa 1: uma mesa por vez, a maior peça que ainda cabe."""
    assert ctx.limite is not None
    teto_area = ctx.largura_cm * ctx.limite
    abertas: list[_Aberta] = []
    pendentes = list(grandes)
    while pendentes:
        mesa = _Aberta([])
        ctx.em("grandes", len(abertas) + 1)
        recusadas: set[tuple] = set()
        for bloco in planejador.blocos(pendentes):
            forma = tuple(u.forma for u in bloco)
            if forma in recusadas:
                continue
            if area_total(mesa.unidades) + planejador.area_bloco(bloco) > teto_area:
                recusadas.add(forma)
                continue
            faixa = ctx.encaixar(mesa.unidades + bloco)
            if ctx.cabe(faixa):
                mesa.unidades += bloco
                mesa.faixa = faixa
            elif not mesa.unidades:
                raise ErroEncaixe(f"{_nomes(bloco)} não cabe numa mesa de {ctx.limite:g} cm")
            else:
                recusadas.add(forma)
        abertas.append(mesa)
        pendentes = _sem(pendentes, mesa.unidades)
    return abertas


def _encher_pequenas(ctx: _Contexto, abertas: list[_Aberta], pequenas: list[Unidade]) -> None:
    """Etapa 2: pequenas nas folgas, da mesa mais curta para a mais longa;
    o que sobrar abre mesas novas."""
    pendentes = list(pequenas)
    for mesa in sorted(abertas, key=lambda m: m.comprimento_cm):
        if not pendentes:
            return
        ctx.em("pequenas", abertas.index(mesa) + 1, len(abertas))
        pendentes = _completar(ctx, mesa, pendentes)
    while pendentes:
        ctx.em("pequenas", len(abertas) + 1)
        mesa = _Aberta([])
        restantes = _completar(ctx, mesa, pendentes)
        if len(restantes) == len(pendentes):
            # nem o lote mínimo coube numa mesa vazia: a maior peça sozinha
            bloco = planejador.blocos(pendentes)[0]
            faixa = ctx.encaixar(bloco)
            if not ctx.cabe(faixa):
                raise ErroEncaixe(f"{_nomes(bloco)} não cabe numa mesa de {ctx.limite:g} cm")
            mesa = _Aberta(list(bloco), faixa)
            restantes = _sem(pendentes, bloco)
        abertas.append(mesa)
        pendentes = restantes


def _completar(ctx: _Contexto, mesa: _Aberta, pendentes: list[Unidade]) -> list[Unidade]:
    """Põe na mesa o que couber de `pendentes`; devolve o que sobrou.

    A mochila propõe o lote; se a faixa passa do limite, fica o que está
    dentro dele (a faixa cortada no limite continua válida — só se tiram
    peças). Um par só entra inteiro.
    """
    assert ctx.limite is not None
    capacidade = planejador.capacidade_cm2(ctx.largura_cm, ctx.limite, DENSIDADE_ALVO)
    while pendentes:
        lote = planejador.mochila(planejador.blocos(pendentes), capacidade - area_total(mesa.unidades), seed=ctx.seed)
        entrou = False
        for _ in range(TENTATIVAS_LOTE):
            if not lote:
                break
            novas = [u for b in lote for u in b]
            faixa = ctx.encaixar(mesa.unidades + novas)
            dentro, _ = _cortar(faixa, ctx.limite)
            ids = {p.unidade.indice for p in dentro}
            base_dentro = all(u.indice in ids for u in mesa.unidades)
            if base_dentro and any(u.indice in ids for u in novas):
                mesa.unidades = [p.unidade for p in dentro]
                mesa.faixa = _faixa_de(dentro, ctx.largura_cm)
                pendentes = _sem(pendentes, mesa.unidades)
                entrou = True
                break
            # nada novo coube (ou a base saiu do limite): lote menor, das
            # menores peças, que encaixam em buracos
            lote = lote[len(lote) // 2 :] if len(lote) > 1 else []
        if not entrou:
            return pendentes
    return pendentes


def _polir(ctx: _Contexto, abertas: list[_Aberta], segundos: float) -> None:
    """Etapa 3: reencaixa cada mesa com mais tempo e fica com a mais curta."""
    if segundos <= 0:
        return
    for i, mesa in enumerate(abertas, start=1):
        if ctx.estourou:
            return
        ctx.em("polimento", i, len(abertas))
        faixa = ctx.encaixar(mesa.unidades, segundos)
        if ctx.cabe(faixa) and faixa.comprimento_cm < mesa.comprimento_cm - EPS_CM:
            mesa.faixa = faixa


def _faixa_de(posicoes: list[Posicao], largura_cm: float) -> Faixa:
    comprimento = comprimento_de(posicoes) - min((p.y for p in posicoes), default=0.0)
    cortada = sum(p.unidade.area_cm2 for p in posicoes)
    aproveitamento = cortada / (largura_cm * comprimento) if comprimento > EPS_CM else 0.0
    return Faixa(comprimento_cm=comprimento, aproveitamento=min(1.0, aproveitamento), posicoes=list(posicoes))


def _cortar(faixa: Faixa, limite_cm: float) -> tuple[list[Posicao], list[Unidade]]:
    """Separa o que cabe até o limite do que passa.

    Devolve (posições que ficam, unidades que saem). Uma peça que cruza a linha
    sai INTEIRA — nunca cortada, como no v1 — e, se é metade de um par, a outra
    metade sai junto: o par não se separa entre mesas (_fechar_pares do v1).
    """
    y0 = min((p.y for p in faixa.posicoes), default=0.0)
    fora = {p.unidade.indice for p in faixa.posicoes if p.y_max - y0 > limite_cm + EPS_CM}
    pares = {p.unidade.par for p in faixa.posicoes if p.unidade.indice in fora and p.unidade.par is not None}
    dentro = [p for p in faixa.posicoes if p.unidade.indice not in fora and p.unidade.par not in pares]
    ficam = {p.unidade.indice for p in dentro}
    return dentro, [p.unidade for p in faixa.posicoes if p.unidade.indice not in ficam]


def _checar_largura(faixa: Faixa) -> None:
    """Peça mais larga que o tecido: o spyrrow a descarta sem aviso, e o v1
    também (nest_worker.findBest devolve null) — lá virava um aviso genérico de
    0% de aproveitamento. Aqui é erro explícito, porque uma mesa sem a peça é
    uma mesa com menos peças do que o plano pediu."""
    if faixa.nao_encaixadas:
        raise ErroEncaixe(f"Peça mais larga que a largura útil do tecido: {_nomes(faixa.nao_encaixadas)}")


def _nomes(unidades: list[Unidade]) -> str:
    return ", ".join(sorted({f"{u.peca or ''} {u.tamanho or ''}".strip() or u.molde_id for u in unidades}))


def _finaliza(abertas: list[_Aberta]) -> list[Mesa]:
    """Monta as mesas na ordem, cada uma ancorada em y = 0."""
    mesas: list[Mesa] = []
    for i, aberta in enumerate(abertas, start=1):
        faixa = aberta.faixa
        assert faixa is not None
        posicoes = desloca(faixa.posicoes, 0.0, -min((p.y for p in faixa.posicoes), default=0.0))
        mesas.append(
            Mesa(
                indice=i,
                comprimento_cm=comprimento_de(posicoes),
                aproveitamento=faixa.aproveitamento,
                pecas=[
                    {
                        "id": p.unidade.molde_id,
                        "x": round(p.x, 3),
                        "y": round(p.y, 3),
                        "rotation": p.rotacao,
                        "polygon": p.unidade.poligono,
                        "espelhada": p.unidade.espelhada,
                        "peca": p.unidade.peca,
                        "tamanho": p.unidade.tamanho,
                        "grupo_nome": p.unidade.grupo_nome,
                    }
                    for p in posicoes
                ],
                unidades=[p.unidade for p in posicoes],
                posicoes=posicoes,
            )
        )
    return mesas
