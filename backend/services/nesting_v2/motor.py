"""motor.py — o v2 de ponta a ponta: preparar → planejar → encaixar → ajustar.

`gerar(pecas, largura_cm, comprimento_max_cm, camadas, tempo_limite_s=30, seed=0)`
devolve a lista de mesas do enfesto. Cada mesa sai no mesmo formato de
mapa_json do motor v1, com uma diferença deliberada:

  * pecas_por_tamanho é DA MESA. O v1 punha a linha do enfesto inteiro em
    todas as partes (nesting_service._pecas_parte: "pecas_por_tamanho continua
    sendo do enfesto inteiro"), o que fazia o card de cada mesa e o relatório
    de produção mostrarem o total do enfesto em cada mesa — e a soma do
    relatório contar o mesmo enfesto uma vez por parte. `pecas_parte` continua
    no mapa (mesmo formato) mas agora é redundante.

Como o K é escolhido
--------------------
O spyrrow minimiza o comprimento mas não tem teto, então quem impõe o limite é
o conjunto: o CP-SAT abre K mesas com capacidade = largura × limite ×
densidade_alvo, o spyrrow enche cada uma, e a mesa que passa do limite tem as
peças que passam devolvidas ao CP-SAT com a restrição extra "esta peça não
volta para esta mesa". Cada volta refaz só as mesas ainda abertas. Se as
`ciclos_max` voltas não fecharem, sobe-se o K e recomeça — mais mesa é mais
tecido, então se prefere sempre a menor K que fecha.

Tempo
-----
`tempo_limite_s` é o orçamento de spyrrow de UMA passada pelas K mesas (K ×
tempo_limite_s / K). As voltas de ajuste (máx. `ciclos_max` por tentativa) e a
escalada de K são etapas separadas que usam o orçamento de cada passada de
novo — sem isso o ciclo de ajuste e a escalada nunca rodariam. O spyrrow não
tem cancelamento: ele termina a mesa em curso mesmo depois do cronômetro, o
estouro é no máximo alguns segundos.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from services.nesting_v2 import planejador
from services.nesting_v2.encaixador import ErroEncaixe, Faixa, Posicao, comprimento_de, desloca, encaixar
from services.nesting_v2.geometria import EPS_CM, Peca, Unidade, area_total, por_tamanho, preparar

# Densidade que se espera de um bom encaixe com polígono real. Medida nos
# dados do pedido 000001: o spyrrow chega a 84% numa faixa sem teto e a 80%
# com o corte em mesas de 150 cm. É o que define o K mínimo do CP-SAT.
DENSIDADE_ALVO = 0.80

# Voltas do ciclo de ajuste por tentativa de K (enunciado do M1).
CICLOS_MAX = 5

# Piso do orçamento de uma mesa, em segundos (o spyrrow trabalha em segundos
# inteiros e um orçamento de 0 não é orçamento).
SEGUNDO_PISO = 1.0


@dataclass
class Mesa:
    """Uma mesa (risco) do enfesto, pronta para virar Encaixe."""

    indice: int
    comprimento_cm: float
    aproveitamento: float
    pecas: list[dict] = field(default_factory=list)
    pecas_por_tamanho: list[dict] = field(default_factory=list)
    unidades: list[Unidade] = field(default_factory=list)
    posicoes: list[Posicao] = field(default_factory=list)

    def mapa_json(self, *, largura_cm: float, camadas: int = 1, **contexto: Any) -> dict:
        """mapa_json no formato do v1 (nesting_service._montar_encaixe).

        `contexto` entra por último, como os `extras` do v1: quem chama passa
        lote_id / tecido_id / tecido_nome / peso_total_kg / pecas_parte /
        total_partes e sobrescreve o que quiser. `parte` (o texto "2/5") só sai
        quando há mais de uma mesa, como no v1.
        """
        mapa: dict[str, Any] = {
            "largura_cm": largura_cm,
            "comprimento_cm": round(self.comprimento_cm, 3),
            "num_camadas": camadas,
            "efficiency": round(self.aproveitamento, 4),
            "placements": self.pecas,
            "parts_count": len(self.pecas),
            "pecas_por_tamanho": self.pecas_por_tamanho,
            "pecas_parte": self._pecas_parte(camadas),
            "parte_numero": self.indice,
            **contexto,
        }
        if int(contexto.get("total_partes") or 1) > 1:
            mapa["parte"] = f"{self.indice}/{int(contexto['total_partes'])}"
        return mapa

    def _pecas_parte(self, camadas: int) -> list[dict]:
        """Detalhe por molde desta mesa — o pecas_parte do v1."""
        acc: dict[tuple, dict] = {}
        for u in self.unidades:
            k = (u.molde_id, u.peca, u.tamanho, u.grupo_nome)
            acc.setdefault(
                k,
                {
                    "molde_id": u.molde_id,
                    "peca": u.peca,
                    "grupo_nome": u.grupo_nome,
                    "tamanho": u.tamanho,
                    "por_camada": 0,
                    "total": 0,
                },
            )["por_camada"] += 1
        for linha in acc.values():
            linha["total"] = linha["por_camada"] * camadas
        return list(acc.values())


# ── Geração ──────────────────────────────────────────────────────────────────


def gerar(
    pecas: list[Peca],
    largura_cm: float,
    comprimento_max_cm: float,
    camadas: int = 1,
    tempo_limite_s: float = 30.0,
    seed: int = 0,
    *,
    margem_cm: float = 0.0,
    densidade_alvo: float = DENSIDADE_ALVO,
    ciclos_max: int = CICLOS_MAX,
    k_max: int | None = None,
) -> list[Mesa]:
    """Divide as peças do enfesto em mesas de comprimento <= limite.

    largura_cm         largura útil do tecido (eixo x das mesas)
    comprimento_max_cm limite da OC: nenhuma mesa pode passar disso
    camadas            quantas camadas do mesmo risco se cortam de uma vez —
                       não muda o plano, entra no mapa_json
    tempo_limite_s     orçamento de spyrrow de cada passada pelas K mesas
    seed               semente do spyrrow e do CP-SAT
    margem_cm          separação mínima entre peças (min_items_separation)
    densidade_alvo     fração da mesa que se espera preencher; define o K mínimo
    ciclos_max         voltas do ajuste por tentativa de K
    k_max              teto de mesas (por padrão: uma por peça, o pior caso)
    """
    unidades = preparar(pecas)
    if not unidades:
        return []

    limite = float(comprimento_max_cm)
    if limite <= 0:
        raise ErroEncaixe(f"Comprimento máximo inválido: {comprimento_max_cm}")
    if largura_cm <= 0:
        raise ErroEncaixe(f"Largura do tecido inválida: {largura_cm}")

    area = area_total(unidades)
    capacidade = planejador.capacidade_cm2(largura_cm, limite, densidade_alvo)
    k = planejador.k_minimo(area, capacidade)
    teto = k_max if k_max is not None else len(unidades)

    inicio = time.perf_counter()
    tentativas: list[str] = []
    while k <= teto:
        mesas, motivo = _tentar(
            unidades, k, largura_cm, limite, capacidade, tempo_limite_s, margem_cm, seed, ciclos_max
        )
        if mesas is not None:
            return mesas
        tentativas.append(f"K={k} ({motivo})")
        k += 1

    raise ErroEncaixe(
        f"Não foi possível encaixar {len(unidades)} peças ({area:.0f} cm²) em mesas de "
        f"{limite:g} × {largura_cm:g} cm com densidade alvo {densidade_alvo:.0%}. "
        f"Tentativas: {'; '.join(tentativas)} em {time.perf_counter() - inicio:.1f}s."
    )


def _tentar(
    unidades: list[Unidade],
    k: int,
    largura_cm: float,
    limite: float,
    capacidade: float,
    tempo_limite_s: float,
    margem_cm: float,
    seed: int,
    ciclos_max: int,
) -> tuple[list[Mesa] | None, str]:
    """Uma tentativa com K mesas. Devolve (mesas, motivo_da_falha).

    `tempo_limite_s` é o orçamento de UMA passada pelas K mesas (K ×
    orçamento por mesa); as voltas de ajuste e a escalada de K são etapas
    separadas e usam o orçamento de cada passada de novo — é o que permite o
    ajuste existir de verdade.

    Uma mesa que fecha (comprimento <= limite) não é mais tocada. Uma que
    estourou volta a ficar ABERTA no ciclo seguinte, com a área das peças que
    passaram do limite marcada como proibida para ela — é a "restrição extra"
    do enunciado. Peças postas saem da lista de pendentes; as demais voltam
    para o planejamento.
    """
    orcao = max(SEGUNDO_PISO, tempo_limite_s / k)
    fechadas: dict[int, Faixa] = {}
    areas: dict[int, float] = {}
    postas: set[int] = set()
    proibidas: set[tuple[int, int]] = set()

    for ciclo in range(1, ciclos_max + 1):
        if len(postas) == len(unidades):
            return _finaliza(fechadas), ""
        # Cada passada (ciclo) tem o ORÇAMENTO TODO de novo. Sem isso o ajuste
        # morria de fome: a primeira passada consumia tudo e qualquer mesa que
        # estourasse por pouco escalava o K em vez de re-planejar com a
        # restrição extra.
        restante = float(tempo_limite_s)
        if restante < SEGUNDO_PISO:
            return None, f"orçamento de {orcao:.0f}s/mesa acabou no ciclo {ciclo}"
        abertos = [t for t in range(k) if t not in fechadas]
        if not abertos:
            return None, f"as {k} mesas fecharam e ainda falta peça (ciclo {ciclo})"

        pendentes = [u for u in unidades if u.indice not in postas]
        capacidades = [capacidade - areas.get(t, 0.0) for t in abertos]
        part = planejador.dividir(pendentes, abertos, capacidades, proibidas=proibidas, seed=seed)
        if part is None:
            return None, f"CP-SAT sem solução no ciclo {ciclo}"

        for j, t in enumerate(abertos):
            grupo = part.mesas[j]
            if not grupo:
                continue
            orcao_mesa = min(orcao, max(SEGUNDO_PISO, restante))
            faixa = encaixar(
                grupo,
                largura_cm,
                segundos=orcao_mesa,
                seed=seed,
                num_workers=1,
                margem_cm=margem_cm,
                nome=f"mesa{t}",
            )
            _checar_largura(faixa)
            restante -= orcao_mesa
            if faixa.comprimento_cm <= limite + EPS_CM:
                fechadas[t] = faixa
                areas[t] = sum(p.unidade.area_cm2 for p in faixa.posicoes)
                postas.update(p.unidade.indice for p in faixa.posicoes)
                continue
            _, fora = _cortar(faixa, limite)
            proibidas.update((u.indice, t) for u in fora)

    if len(postas) == len(unidades):
        return _finaliza(fechadas), ""
    return None, f"não fechou em {ciclos_max} ciclos"


def _cortar(faixa: Faixa, limite_cm: float) -> tuple[list[Posicao], list[Unidade]]:
    """Separa o que cabe até o limite do que passa.

    Devolve (posições que ficam, unidades que saem). Uma peça que cruza a linha
    vai para a próxima mesa INTEIRA — nunca cortada, como no v1 — e, se ela é
    metade de um par, a outra metade vai junto: o par não se separa entre
    mesas (é o _fechar_pares do v1).
    """
    dentro = [p for p in faixa.posicoes if p.y_max <= limite_cm + EPS_CM]
    fora = [p for p in faixa.posicoes if p.y_max > limite_cm + EPS_CM]
    if not fora:
        return dentro, []
    pares = {p.unidade.par for p in fora if p.unidade.par is not None}
    if pares:
        dentro = [p for p in dentro if p.unidade.par not in pares]
        fora = [p for p in faixa.posicoes if p.unidade.par in pares or p.y_max > limite_cm + EPS_CM]
    return dentro, [p.unidade for p in fora]


def _checar_largura(faixa: Faixa) -> None:
    """Peça mais larga que o tecido: o spyrrow a descarta sem aviso, e o v1
    também (nest_worker.findBest devolve null) — lá virava um aviso genérico de
    0% de aproveitamento. Aqui é erro explícito, porque uma mesa sem a peça é
    uma mesa com menos peças do que o plano pediu."""
    if not faixa.nao_encaixadas:
        return
    nomes = sorted({f"{u.peca or ''} {u.tamanho or ''}".strip() or u.molde_id for u in faixa.nao_encaixadas})
    raise ErroEncaixe(f"Peça mais larga que a largura útil do tecido: {', '.join(nomes)}")


def _finaliza(fechadas: dict[int, Faixa]) -> list[Mesa]:
    """Monta as mesas na ordem, cada uma ancorada em y = 0."""
    mesas: list[Mesa] = []
    for i, t in enumerate(sorted(fechadas), start=1):
        faixa = fechadas[t]
        posicoes = desloca(faixa.posicoes, 0.0, -min((p.y for p in faixa.posicoes), default=0.0))
        unidades = [p.unidade for p in posicoes]
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
                        "peca": p.unidade.peca,
                        "tamanho": p.unidade.tamanho,
                        "grupo_nome": p.unidade.grupo_nome,
                    }
                    for p in posicoes
                ],
                pecas_por_tamanho=por_tamanho(unidades),
                unidades=unidades,
                posicoes=posicoes,
            )
        )
    return mesas
