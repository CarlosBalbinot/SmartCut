"""nesting_v2 — motor de encaixe v2 (M1), EMBUTIDO no backend Python.

Motivo: o motor v1 (SVGnest via Node.js, skyline por bounding box) desperdiça
tecido demais quando há limite de comprimento de mesa. O v2 usa dois
algoritmos de verdade:

  * spyrrow (MIT) — strip packing de peças irregulares, minimiza o
    comprimento da faixa. É o motor de cada mesa.
  * OR-Tools CP-SAT (Apache-2.0) — decide como dividir as peças do enfesto em
    K mesas de comprimento <= limite, equilibrando área e respeitando pares.

Fluxo de `motor.gerar()`:

  1. PREPARAÇÃO   geometria.preparar  — molde → unidade de corte (polígono
     real, allowed_orientations pelo sentido do fio, par espelhado como item
     próprio, margem via min_items_separation).
  2. PLANEJAMENTO planejador.dividir  — CP-SAT separa as unidades em K mesas
     (capacidade = largura × limite × densidade_alvo), K mínimo viável.
  3. ENCAIXE      encaixador.encaixar — spyrrow em cada mesa (strip_height =
     largura útil do tecido), minimizando o comprimento.
  4. AJUSTE       motor._montar       — mesa acima do limite tem as peças que
     passam devolvidas ao CP-SAT (restrição extra: não voltam para a mesma
     mesa) e tudo é reencaixado; no máximo `ciclos_max` ciclos por tentativa.
  5. SAÍDA        motor.Mesa.mapa_json — mesmo formato do mapa_json do v1, com
     pecas_por_tamanho DA MESA (o v1 repetia o do enfesto em cada parte).

O motor v1 (nesting/nesting_bridge.py + services/nesting_service.py) NÃO é
alterado: o v2 convive com ele e é usado só por quem o chamar.
"""

from services.nesting_v2.geometria import Peca, Unidade, preparar
from services.nesting_v2.motor import ErroEncaixe, Mesa, gerar

__all__ = ["ErroEncaixe", "Mesa", "Peca", "Unidade", "gerar", "preparar"]
