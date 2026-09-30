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
  3. par espelhado como item próprio: `par` vira DUAS unidades. No
     enfesto simples (todas as camadas com o lado direito para cima) a 2ª é
     o espelho da 1ª — direita e esquerda no mesmo desenho. No enfesto duplo
     (Peca.espelhar_par = False) as duas são iguais: as camadas alternam o
     lado e cada par de camadas já corta direita e esquerda.
     `par_sem_espelho` são duas peças IGUAIS, NUNCA espelhadas, em qualquer
     enfesto (ex.: dois bolsos idênticos). Se a peça for assimétrica, o
     enfesto duplo nem é oferecido (decisor.analisar) — metade das camadas a
     cortaria virada;
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

    id            id do molde — vai para placement.id
    poligono      contorno em cm no referencial do app, ANTES de rotacao_base.
                  Molde sem geometria: nesting_service._extrair_poligono já
                  devolve o retângulo de fallback (pela área)
    quantidade    total de cópias FÍSICAS deste molde a cortar (para par, o
                  total das duas metades — precisa ser par)
    rotacoes      ângulos permitidos em graus (regra do sentido do fio)
    tipo_corte    simples | par (2 espelhadas) | par_sem_espelho (2 iguais)
    rotacao_base  giro do cadastro, aplicado na origem (o spyrrow gira em
                  torno da origem do próprio item — ver encaixador)
    espelhar_par  True no enfesto simples (a 2ª cópia do `par` sai
                  espelhada); False no enfesto duplo (duas cópias iguais — a
                  alternância das camadas faz direita e esquerda). Não se
                  aplica a `par_sem_espelho`, que nunca espelha
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
    espelhar_par: bool = True


def espelha_segunda_copia(tipo_corte: str, espelhar_par: bool = True) -> bool:
    """A 2ª cópia de cada par deste molde sai espelhada no desenho? Só no
    `par` e só no enfesto simples; `par_sem_espelho` nunca espelha."""
    return espelhar_par and tipo_corte == "par"


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
    def altura_cm(self) -> float:
        """Extensão no comprimento da mesa (y) — o fio vertical só gira 180°,
        então é a mesma em qualquer rotação permitida (0/180)."""
        _, min_y, _, max_y = bbox(self.poligono)
        return max_y - min_y

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


def eixo_do_fio(rotacoes: tuple[float, ...]) -> str:
    """Eixo do molde (no referencial dele) que fica paralelo ao fio do tecido.

    O fio corre no COMPRIMENTO da mesa (y). Com as rotações da regra do v1
    (nesting_service._rotacoes), só o fio horizontal (90/270) põe o eixo x do
    molde no comprimento; vertical, 45° e sem restrição usam o eixo y.
    """
    if rotacoes and all(float(r) % 180 == 90 for r in rotacoes):
        return "x"
    return "y"


def espelhar(pontos: list[list[float]], eixo_fio: str = "y") -> list[list[float]]:
    """Espelho da peça sobre uma reta PARALELA AO FIO, pelo centro do bbox.

    É o "flip no eixo do fio" do par: a segunda metade de uma peça de `par`
    (manga esquerda/direita, frente esquerda/direita) é a primeira virada
    sobre o fio, e continua no fio depois do espelho. Fio em y → x vira
    2·cx − x; fio em x → y vira 2·cy − y. O espelho muda a quiralidade, não a
    área nem o bounding box.
    """
    min_x, min_y, max_x, max_y = bbox(pontos)
    if eixo_fio == "x":
        eixo = (min_y + max_y) / 2.0
        return [[x, 2 * eixo - y] for x, y in pontos]
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
    cópias viram pares (metade original + metade espelhada ou idêntica —
    ver espelha_segunda_copia) ligados pelo mesmo `par`. Devolve [] se não
    há o que cortar.
    """
    unidades: list[Unidade] = []
    proximo_par = 0
    for p in pecas:
        if p.quantidade <= 0 or len(p.poligono) < 3:
            continue
        base = normalizar(rotacionar(p.poligono, p.rotacao_base))
        area_base = area(base)
        eh_par = p.tipo_corte in PARES
        espelha = eh_par and espelha_segunda_copia(p.tipo_corte, p.espelhar_par)
        n = int(p.quantidade)
        if eh_par and n % 2:
            raise ValueError(f"Molde {p.id}: tipo_corte '{p.tipo_corte}' com quantidade ímpar ({n})")
        grupo = None
        for k in range(n):
            if eh_par and k % 2 == 0:
                grupo = proximo_par
                proximo_par += 1
            espelhada = espelha and k % 2 == 1
            poligono = espelhar(base, eixo_do_fio(p.rotacoes)) if espelhada else base
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


def por_molde(unidades: list[Unidade], camadas: int = 1) -> list[dict]:
    """Moldes que UMA mesa corta: FRENTE G x1, COSTAS M x2...

    A tabela da mesa é por molde, não por tamanho de roupa: uma mesa pode ter
    a FRENTE de um G e não as COSTAS dele, então a "grade" (P1 M2 G3) não
    descreve a mesa. `por_camada` conta as peças físicas da mesa (as duas
    metades de um par contam 2; `espelhadas` diz quantas são a metade virada);
    `total` = por_camada × camadas.
    """
    acc: dict[tuple, dict] = {}
    for u in unidades:
        linha = acc.setdefault(
            (u.molde_id, u.peca, u.tamanho, u.grupo_nome),
            {
                "molde_id": u.molde_id,
                "peca": u.peca,
                "grupo_nome": u.grupo_nome,
                "tamanho": u.tamanho,
                "por_camada": 0,
                "espelhadas": 0,
                "total": 0,
            },
        )
        linha["por_camada"] += 1
        linha["espelhadas"] += int(u.espelhada)
    for linha in acc.values():
        linha["total"] = linha["por_camada"] * camadas
    return list(acc.values())


def grade_por_tamanho(unidades: list[Unidade], camadas: int = 1) -> list[dict]:
    """Grade do ENFESTO inteiro por tamanho — só para o resumo do enfesto.

    É o que o v1 punha (errado) em cada parte, no formato do `pecas_por_tamanho`
    dele. Conta peças físicas por (grupo, tamanho) somando TODAS as mesas;
    `total` = pecas × camadas. `sobra` é 0: quem decide sobra é o plano de
    enfesto (services.plano_enfesto), que entrega só o que deve ser cortado.
    """
    acc: dict[tuple[str | None, str | None], int] = {}
    for u in unidades:
        k = (u.grupo_nome, u.tamanho)
        acc[k] = acc.get(k, 0) + 1
    return [{"grupo_nome": g, "tamanho": t, "pecas": n, "total": n * camadas, "sobra": 0} for (g, t), n in acc.items()]
