"""nesting_v2 — motor de encaixe (spyrrow + OR-Tools), EMBUTIDO no backend Python.

É o ÚNICO motor do sistema: o antigo (Node.js, skyline por bounding box)
gastava tecido demais quando há limite de comprimento de mesa. O v2 usa
dois algoritmos de verdade:

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
  5. SAÍDA        motor.Resultado — mesas no formato do mapa_json (o mesmo
      formato de sempre), com a tabela da mesa POR MOLDE; a grade por tamanho
      só no resumo do enfesto. Tempo, chamadas do spyrrow e pico de memória
      vêm junto.

A escolha do perfil de tempo (RAPIDO/EQUILIBRADO/MAXIMO, ou AUTOMATICO por
orçamento de tempo — services/planejamento/custo.py) e a nova tentativa em caso
de falha ficam em services/nesting_service.py.
"""

from services.nesting_v2 import encaixador, planejador
from services.nesting_v2.geometria import Peca, Unidade, preparar
from services.nesting_v2.motor import ErroEncaixe, Mesa, Resultado, gerar

# spyrrow/ortools ausentes (exe montado sem o v2) não derrubam o import: o
# motor fica INDISPONÍVEL e o serviço de encaixe avisa que é preciso
# reinstalar as dependências (não há motor alternativo — o v1 foi removido).
_ERROS = [e for e in (encaixador.ERRO_IMPORT, planejador.ERRO_IMPORT) if e]
DISPONIVEL = not _ERROS


def diagnostico() -> str:
    """Linha para o log do boot: versões das bibliotecas ou o erro de import."""
    if _ERROS:
        return f"Motor v2 INDISPONÍVEL: {'; '.join(_ERROS)} — reinstale as dependências"
    import ortools

    return f"Motor v2 disponível (spyrrow {getattr(encaixador.spyrrow, '__version__', '?')}, ortools {ortools.__version__})"


__all__ = ["DISPONIVEL", "ErroEncaixe", "Mesa", "Peca", "Resultado", "Unidade", "diagnostico", "gerar", "preparar"]
