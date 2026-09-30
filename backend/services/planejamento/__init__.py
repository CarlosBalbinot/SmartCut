"""planejamento — o plano de CORTE (as decisões que vêm antes do motor).

Tudo aqui é puro: nenhuma consulta, nenhum encaixe, nenhum spyrrow. É o
caminho que roda antes de `services/nesting_v2` e que o motor só executa.

Módulos:
  * custo — quanto tempo cada risco de corte vai levar e qual perfil de tempo
    (Rápido / Equilibrado / Máximo) cabe no orçamento da Ordem de Corte
    (Configurações > Produção > "Tempo limite da ordem de corte (s)").

O resto do plano de corte (o grupo multicor e o CP-SAT dos riscos) entra aqui
também; enquanto isso, este pacote é o que decide a qualidade.
"""

from services.planejamento.custo import (
    MULTIPLICADORES as MULTIPLICADORES,
    PERFIS as PERFIS,
    Orcamento as Orcamento,
    estimar_mesas as estimar_mesas,
    estimar_segundos as estimar_segundos,
)
