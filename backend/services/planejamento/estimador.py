"""estimador.py — comprimento e mesas de um risco SEM rodar o motor.

O plano de corte (plano_corte.py) precisa comparar centenas de riscos
candidatos; rodar o spyrrow em cada um levaria horas. A estimativa sai da
ÁREA e do número de MESAS:

    miolo       = área / (largura × APROVEITAMENTO)
    mesas       = ⌈ miolo / (limite × OCUPACAO_MESA − PERDA_MESA_CM) ⌉
    comprimento = miolo + mesas × PERDA_MESA_CM

O desperdício de um risco não está no miolo (onde as peças se encaixam bem),
está nas PONTAS de cada mesa: cada mesa começa e termina com peças que não
têm com quem se encaixar. Por isso um risco muito longo não aproveita melhor
sem limite — ele paga uma ponta a cada mesa em que é dividido. E o motor
não enche cada mesa até o limite (divide o risco onde as peças deixam):
OCUPACAO_MESA é a fração do limite que uma mesa usa, em média.

Ajuste com os riscos gravados da OC-0004 (motor v2, mesa de 150 cm, MAXXI
150 cm), comprimento real × estimado:

    risco            área (cm²)   mesas real/est.   real (cm)   estimado (cm)
    P1 M2 G2 GG1        68 017         5 / 5            583          584
    P1 G3 GG1           57 691         5 / 5            503          503
    G1 GG2              36 390         3 / 3            331          315

Em tecido mais estreito o erro cresce (CANELADO 130 cm: P1 M3 G4 GG2 estima
1 137 cm para 1 301 cm reais) — mas o plano compara riscos do MESMO tecido,
e errar igual para todos os candidatos é o que importa. O motor, depois, dá
o número de verdade; a estimativa só escolhe o plano.

Não é o mesmo número de custo.DENSIDADE (0,55): aquele é pessimista de
propósito, porque serve para não estourar o PRAZO.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

APROVEITAMENTO = 0.85
PERDA_MESA_CM = 10.0
OCUPACAO_MESA = 0.78


def area_risco(conjuntos: Mapping[str, int], area_por_tamanho: Mapping[str, float]) -> float:
    """cm² de UMA camada do risco: conjuntos × área do conjunto do tamanho
    (a área do conjunto já conta as peças físicas — par vale 2)."""
    return sum(n * float(area_por_tamanho[t]) for t, n in conjuntos.items() if n > 0)


def estimar(
    conjuntos: Mapping[str, int],
    area_por_tamanho: Mapping[str, float],
    largura_cm: float,
    limite_cm: float,
) -> tuple[float, int]:
    """(comprimento em cm, mesas) de um enfesto do risco — o risco é dividido
    em trechos <= limite_cm, e cada trecho paga PERDA_MESA_CM."""
    if largura_cm <= 0:
        raise ValueError("largura do tecido deve ser positiva")
    util = limite_cm * OCUPACAO_MESA - PERDA_MESA_CM
    if util <= 0:
        raise ValueError("limite da mesa menor que a perda de ponta")
    miolo = area_risco(conjuntos, area_por_tamanho) / (largura_cm * APROVEITAMENTO)
    if miolo <= 0:
        return 0.0, 0
    mesas = max(1, math.ceil(miolo / util - 1e-9))
    return miolo + mesas * PERDA_MESA_CM, mesas
