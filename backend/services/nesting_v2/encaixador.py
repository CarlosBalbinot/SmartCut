"""encaixador.py — etapa 3: o spyrrow enche uma mesa.

O spyrrow faz *strip packing*: a faixa tem altura fixa (`strip_height`, aqui a
largura útil do tecido) e o comprimento é o que ele minimiza. Uma mesa = uma
StripPackingInstance.

O motor v1 (skyline por bounding box, em Node.js) posicionava pelo bounding
box; aqui entra o polígono real, que é a maior parte do ganho.

Troca de referencial (o ponto que mais custa errar):
  spyrrow:  x = ao longo da faixa (o comprimento), y = dentro da altura fixa
            solução = R(rotation)·forma + translation
  SmartCut: x = largura do tecido, y = comprimento da mesa
            placement = R(rotation)·poligono, ancorado pelo canto
            inferior-esquerdo do bbox rotacionado em (x, y)
Passamos a forma TRANSPOSTADA ((x, y) -> (y, x)) e voltamos com a mesma
transposição, que é a própria inversa. A troca é uma reflexão, então ela
troca o sentido do giro: o ângulo que volta para o mapa_json é o do spyrrow
com o sinal trocado (0 e 180 — os únicos do sentido do fio vertical — ficam
iguais). Como o ângulo do v1 também é lido "a partir do polígono", o
consumidor reconstrói exatamente os mesmos pontos.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import spyrrow

from services.nesting_v2.geometria import EPS_CM, Unidade, rotacionar

# Um Item por forma+rotações distintas; o id do spyrrow é o índice do grupo.
_Item = tuple[spyrrow.Item, list[Unidade]]


class ErroEncaixe(RuntimeError):
    """O spyrrow recusou a instancia (peça maior que a faixa, forma inválida)."""


@dataclass
class Posicao:
    """Uma unidade colocada, já no referencial do app (x = largura)."""

    unidade: Unidade
    x: float
    y: float
    rotacao: float
    pontos: list[list[float]]

    @property
    def y_max(self) -> float:
        return max(p[1] for p in self.pontos)


@dataclass
class Faixa:
    """Uma mesa encaixada: comprimento, aproveitamento e as peças dentro."""

    comprimento_cm: float
    aproveitamento: float
    posicoes: list[Posicao] = field(default_factory=list)
    nao_encaixadas: list[Unidade] = field(default_factory=list)


def _transpor(pontos: list[list[float]]) -> list[tuple[float, float]]:
    return [(y, x) for x, y in pontos]


def _normaliza_grau(graus: float) -> float:
    """[0, 360) — o spyrrow devolve -180.0; o v1 só emite 0/90/180/270 e o
    PDF/Visualizador rotulam a peça como girada com qualquer valor diferente
    de zero, então o ângulo tem que ser o canônico."""
    return float(graus) % 360.0


def _itens(unidades: list[Unidade]) -> list[_Item]:
    """Agrupa as unidades por forma: uma por Item, com demand = cópias."""
    grupos: dict[tuple, list[Unidade]] = {}
    for u in unidades:
        grupos.setdefault(u.forma, []).append(u)
    itens: list[_Item] = []
    for i, (forma, do_grupo) in enumerate(grupos.items()):
        pontos, rotacoes = forma
        # o spyrrow fecha o anel sozinho: repetir o primeiro ponto é opcional
        # e a wheel aceita, mas tirar evita um vértice degenerado
        if len(pontos) > 1 and pontos[0] == pontos[-1]:
            pontos = pontos[:-1]
        itens.append(
            (
                spyrrow.Item(
                    str(i),
                    [(float(x), float(y)) for x, y in _transpor([list(p) for p in pontos])],
                    demand=len(do_grupo),
                    allowed_orientations=list(rotacoes),
                ),
                do_grupo,
            )
        )
    return itens


def encaixar(
    unidades: list[Unidade],
    largura_cm: float,
    *,
    segundos: float = 10.0,
    seed: int = 0,
    num_workers: int = 1,
    margem_cm: float = 0.0,
    nome: str = "smartcut",
) -> Faixa:
    """Encaixa as unidades numa faixa de altura `largura_cm`.

    segundos    orçamento do spyrrow para ESTA mesa (o motor.py reparte o
                tempo limite total entre as mesas)
    seed        com num_workers=1 e converged=True o resultado é
                reproduzível; ver `convergiu` no retorno de Faixa
    num_workers 1 por padrão: com vários workers o sparrow escalona o
                trabalho entre threads e o resultado muda a cada execução
    margem_cm   separação mínima entre peças (e também das bordas da faixa, por
                isso ela come largura). 0 = peças encostam, como no v1.

    Peça mais larga que a faixa não é encaixada: o spyrrow a devolve em
    `nao_encaixadas` em vez de falhar (o v1 também a descartava, em silêncio).
    """
    if not unidades:
        return Faixa(comprimento_cm=0.0, aproveitamento=0.0)
    if largura_cm <= 0:
        raise ErroEncaixe(f"largura do tecido inválida: {largura_cm}")

    itens = _itens(unidades)
    inst = spyrrow.StripPackingInstance(nome, strip_height=float(largura_cm), items=[i for i, _ in itens])
    cfg = spyrrow.StripPackingConfig(
        early_termination=True,
        total_computation_time=max(1, int(round(segundos))),
        num_workers=max(1, int(num_workers)),
        seed=int(seed),
        min_items_separation=float(margem_cm),
    )
    try:
        sol = inst.solve(cfg)
    except (ValueError, RuntimeError) as exc:
        raise ErroEncaixe(f"spyrrow recusou a instancia: {exc}") from exc

    por_id = {item.id: grupo for item, grupo in itens}
    # Um placed_item por cópia: cada Item com demand n devolve n cópias, que
    # são indistinguíveis — casa com as unidades do grupo na ordem.
    disponiveis: dict[str, list[Unidade]] = {k: list(v) for k, v in por_id.items()}
    poligonos = {item.id: grupo[0].poligono for item, grupo in itens}

    posicoes: list[Posicao] = []
    for pl in sol.placed_items:
        grupo = disponiveis.get(pl.id)
        if not grupo:  # pragma: no cover - spyrrow não inventa peça
            continue
        unidade = grupo.pop(0)
        tx, ty = float(pl.translation[0]), float(pl.translation[1])
        pontos = _volta(poligonos[pl.id], float(pl.rotation), tx, ty)
        posicoes.append(
            Posicao(
                unidade=unidade,
                x=min(p[0] for p in pontos),
                y=min(p[1] for p in pontos),
                rotacao=_normaliza_grau(-float(pl.rotation)),
                pontos=pontos,
            )
        )

    nao_encaixadas = [u for grupo in disponiveis.values() for u in grupo]
    comprimento = max((p.y_max for p in posicoes), default=0.0)
    cortadas = sum(p.unidade.area_cm2 for p in posicoes)
    aproveitamento = cortadas / (largura_cm * comprimento) if comprimento > EPS_CM else 0.0
    return Faixa(
        comprimento_cm=comprimento,
        aproveitamento=min(1.0, aproveitamento),
        posicoes=posicoes,
        nao_encaixadas=nao_encaixadas,
    )


def _volta(poligono: list[list[float]], rotacao: float, tx: float, ty: float) -> list[list[float]]:
    """Ponto do spyrrow → ponto do app.

    O spyrrow posiciona a FORMA (transposta) já rotacionada e somada à
    translation; desfazemos a rotação, tiramos a translação e voltamos com a
    transposição, obtendo R(-rotacao)·poligono + (ty, tx).
    """
    pts = rotacionar(poligono, -rotacao)
    return [[x + ty, y + tx] for x, y in pts]


def comprimento_de(posicoes: list[Posicao]) -> float:
    """Extensão da mesa em y (o comprimento) — a maior ponta das peças."""
    return max((p.y_max for p in posicoes), default=0.0)


def desloca(posicoes: list[Posicao], dx: float, dy: float) -> list[Posicao]:
    """Move a mesa inteira (usado para ancorar a faixa em y = 0)."""
    return [
        Posicao(p.unidade, p.x + dx, p.y + dy, p.rotacao, [[x + dx, y + dy] for x, y in p.pontos]) for p in posicoes
    ]
