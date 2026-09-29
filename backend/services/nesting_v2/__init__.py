"""nesting_v2 — motor de encaixe v2 (M1), EMBUTIDO no backend Python.

Motivo: o motor v1 (SVGnest via Node.js, skyline por bounding box) desperdiça
tecido demais quando há limite de comprimento de mesa. O v2 usa dois
algoritmos de verdade:

  * spyrrow (MIT) — strip packing de peças irregulares, minimiza o
    comprimento da faixa. É o motor de cada mesa.
  * OR-Tools CP-SAT (Apache-2.0) — decide como dividir as peças do enfesto em
    K mesas de comprimento <= limite, equilibrando área e respeitando pares.

Fluxo de `motor.gerar()` (M1-B):

  1. PREPARAÇÃO   geometria.preparar  — molde → unidade de corte (polígono
     real, allowed_orientations pelo sentido do fio, segunda metade de `par`
     espelhada sobre o eixo do fio, margem via min_items_separation).
  2. GRANDES      motor._encher_grandes — peças que não cabem duas vezes no
     comprimento enchem uma mesa por vez (spyrrow diz se coube).
  3. PEQUENAS     motor._encher_pequenas — CP-SAT (planejador.mochila) propõe
     o lote para a folga de cada mesa; o spyrrow encaixa e o que passar do
     limite volta para a fila.
  4. POLIMENTO    motor._polir — reencaixe final de cada mesa com mais tempo.
  5. SAÍDA        motor.Resultado — mesas no formato do mapa_json do v1, com a
     tabela da mesa POR MOLDE; a grade por tamanho só no resumo do enfesto.
     Tempo, chamadas do spyrrow e pico de memória vêm junto.

O motor v1 (nesting/nesting_bridge.py + services/nesting_service.py) NÃO é
alterado: o v2 convive com ele e é usado só por quem o chamar.
"""

from services.nesting_v2.geometria import Peca, Unidade, preparar
from services.nesting_v2.motor import ErroEncaixe, Mesa, Resultado, gerar

__all__ = ["ErroEncaixe", "Mesa", "Peca", "Resultado", "Unidade", "gerar", "preparar"]
