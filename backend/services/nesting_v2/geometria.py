"""geometria.py — etapa 1: molde vira unidade de corte.

Referencial (o mesmo do motor v1, do Visualizador e do PDF — não mudar):
  x = LARGURA do tecido, 0..largura_cm, o eixo transversal da mesa
  y = COMPRIMENTO da mesa, o eixo que o motor minimiza
Um placement do v1 carrega o polígono JÁ com rotacao_base, a rotação e o
canto inferior-esquerdo do bounding box rotacionado em (x, y) — e o
consumidor refaz a conta (rotaciona na origem e ancora o bbox em x, y). O v2
devolve exatamente esse mesmo contrato.

O spyrrow trabalha com a faixa no eixo x e a altura fixa em y, ou seja
transposto em relação a este referencial. A troca fica em encaixador.py.

Decisões desta etapa (enunciado do M1):

  1. polígono REAL (geometria_json), nunca o bounding box;
  2. rotações pelo sentido do fio → allowed_orientations — a regra é a mesma
     do v1 (nesting_service._rotacoes), quem chama passa em Peca.rotacoes;
  3. par espelhado como item próprio: `par` vira DUAS unidades, uma o
     espelho da outra; `par_sem_espelho` vira duas unidades iguais. O v1
     colocava as duas cópias como a mesma peça (items 2/3 do molde, _MULT);
  4. margem entre peças: o spyrrow tem min_items_separation, então não é
     preciso buffer com shapely.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# tipo_corte que corta DUAS peças de um mesmo molde (a segunda completa o par)
PARES = ("par", "par_sem_espelho")

Ponto = tuple[float, float]

# Folga (cm) nas comparações de limite: o topo de uma mesa é recalculado aqui
# com a mesma conta da área, e cos/sin podem diferir no último bit.
EPS_CM = 1e-3


# ── Modelo ───────────────────────────────────────────────────────────────────


@dataclass
class Peca:
    """Linha de entrada do motor: um molde, quantas vezes e com que rotações.

    id            id do molde — vai para placement.id, como no v1
    poligono      contorno em cm no referencial do app, ANTES de rotacao_base.
                  Molde sem geometria: use nesting_bridge.build_polygon, que
                  já tem o fallback do retângulo pela área (mesmo do v1)
    quantidade    total de cópias FÍSICAS deste molde a cortar (para par, o
                  total das duas metades — precisa ser par)
    rotacoes      ângulos permitidos em graus (regra do sentido do fio)
    tipo_corte    simples | par | par_sem_espelho
    rotacao_base  giro do cadastro, aplicado na origem (o spyrrow gira em
                  torno da origem do próprio item — ver encaixador)
    """

    id: str
    poligono: list[list[float]]
    quantidade: int = 1
    rotacoes: tuple[float, ...] = (0.0, 180.0)
    tipo_corte: str = "simples"
    rotacao_base: float = 0.0
    peca: str | None = None
    tamanho: str | None = None
    grupo_nome: str | None = None


@dataclass
class Unidade:
    """Uma peça física a cortar — 1 marcação no papel.

    Uma Peca vira 1 Unidade (simples) ou 2 (par / par sem espelho). O campo
    `par` é o mesmo número nas duas metades de um par: elas precisam cair na
    MESMA mesa, como no v1 (nesting_service._fechar_pares) — mas podem ficar
    em qualquer posição dentro dela, que o v1 não permitia.
    """

    indice: int
    molde_id: str
    poligono: list[list[float]]
    rotacoes: tuple[float, ...]
    area_cm2: float
    par: int | None
    espelhada: bool
    peca: str | None
    tamanho: str | None
    grupo_nome: str | None

    @property
    def forma(self) -> tuple[tuple[Ponto, ...], tuple[float, ...]]:
        """Chave de identidade geométrica: duas unidades com a mesma `forma` e
        as mesmas `rotacoes` viram um único Item do spyrrow com demand > 1."""
        return (tuple(tuple(p) for p in self.poligono), tuple(float(r) for r in self.rotacoes))


# ── Geometria ────────────────────────────────────────────────────────────────


def area(poligono: list[list[float]]) -> float:
    """Área do polígono (cordão / shoelace). Mesma conta do v1."""
    n = len(poligono)
    dobro = sum(poligono[i][0] * poligono[(i + 1) % n][1] - poligono[(i + 1) % n][0] * poligono[i][1] for i in range(n))
    return abs(dobro) / 2.0


def bbox(pontos: list[list[float]]) -> tuple[float, float, float, float]:
    """(min_x, min_y, max_x, max_y)."""
    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    return min(xs), min(ys), max(xs), max(ys)


def rotacionar(pontos: list[list[float]], graus: float) -> list[list[float]]:
    """Gira em torno da ORIGEM, em graus.

    É a convenção do spyrrow e a que todo consumidor do mapa_json usa (o
    relatório e o Visualizador giram na origem e ancoram o bbox em x, y). O
    v1 girava o rotacao_base em torno do centro do bbox, o que dá o mesmo
    desenho com outra origem.
    """
    if not graus or not graus % 360:
        return [[float(x), float(y)] for x, y in pontos]
    rad = math.radians(graus)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    return [[x * cos_a - y * sin_a, x * sin_a + y * cos_a] for x, y in pontos]


def espelhar(pontos: list[list[float]]) -> list[list[float]]:
    """Espelho esquerda<->direita, em torno do centro do bounding box.

    O eixo do espelho é o do COMPRIMENTO (x = largura): o par de uma peça
    simétrica é a outra metade lado a lado no tecido, como na figura. O
    espelho muda a quiralidade, não a área nem o bounding box — para o
    empacotador é a mesma pegada, então o resultado não muda; o espelho existe
    para a peça cortada ser a peça de verdade.
    """
    min_x, _, max_x, _ = bbox(pontos)
    eixo = (min_x + max_x) / 2.0
    return [[2 * eixo - x, y] for x, y in pontos]


def normalizar(pontos: list[list[float]]) -> list[list[float]]:
    """Desloca para o canto (0, 0) do bounding box.

    O spyrrow posiciona pelo canto do item, não pela origem do molde, então o
    polígono das unidades carrega coordenadas absolutas do arquivo de
    geometria (daqui saem valores como x=22..77). Anchorar no zero deixa o
    cálculo de bbox e de sobreposição legível e não muda nada no resultado.
    """
    min_x, min_y, _, _ = bbox(pontos)
    return [[x - min_x, y - min_y] for x, y in pontos]


# ── Preparação ───────────────────────────────────────────────────────────────


def preparar(pecas: list[Peca]) -> list[Unidade]:
    """Expande as linhas de entrada em unidades de corte.

    `Peca.quantidade` é o total de cópias físicas; para tipo_corte par as
    cópias viram pares (metade original + metade espelhada ou idêntica)
    ligados pelo mesmo `par`. Devolve [] se não há o que cortar.
    """
    unidades: list[Unidade] = []
    proximo_par = 0
    for p in pecas:
        if p.quantidade <= 0 or len(p.poligono) < 3:
            continue
        base = normalizar(rotacionar(p.poligono, p.rotacao_base))
        area_base = area(base)
        eh_par = p.tipo_corte in PARES
        n = int(p.quantidade)
        if eh_par and n % 2:
            raise ValueError(f"Molde {p.id}: tipo_corte '{p.tipo_corte}' com quantidade ímpar ({n})")
        grupo = None
        for k in range(n):
            if eh_par and k % 2 == 0:
                grupo = proximo_par
                proximo_par += 1
            espelhada = eh_par and p.tipo_corte == "par" and k % 2 == 1
            poligono = espelhar(base) if espelhada else base
            unidades.append(
                Unidade(
                    indice=len(unidades),
                    molde_id=p.id,
                    poligono=poligono,
                    rotacoes=tuple(float(r) for r in p.rotacoes),
                    area_cm2=area_base,
                    par=grupo,
                    espelhada=espelhada,
                    peca=p.peca,
                    tamanho=p.tamanho,
                    grupo_nome=p.grupo_nome,
                )
            )
    return unidades


def area_total(unidades: list[Unidade]) -> float:
    return sum(u.area_cm2 for u in unidades)


def por_tamanho(unidades: list[Unidade]) -> list[dict]:
    """pecas_por_tamanho DESTA mesa, no formato que o mapa_json do v1 usa.

    Correção do bug do v1: lá a linha era do ENFESTO inteiro e ia repetida em
    todas as partes, então o card de cada mesa e o relatório de produção
    mostravam o total do enfesto em cada mesa. Aqui a linha é da mesa.

    Uma mesa é UMA camada, então `conjuntos` (peças por camada no relatório) e
    `pecas` são o mesmo número aqui; `total` = pecas × camadas é calculado de
    fora. `sobra` é 0: quem decide sobra é o plano de enfesto
    (services.plano_enfesto), e ele entrega só as peças que deben ser cortadas.
    """
    acc: dict[tuple[str | None, str | None], int] = {}
    ordem: list[tuple[str | None, str | None]] = []
    for u in unidades:
        k = (u.grupo_nome, u.tamanho)
        if k not in acc:
            acc[k] = 0
            ordem.append(k)
        acc[k] += 1
    return [
        {
            "grupo_nome": g,
            "tamanho": t,
            "conjuntos": acc[(g, t)],
            "pecas": acc[(g, t)],
            "sobra": 0,
        }
        for g, t in ordem
    ]
