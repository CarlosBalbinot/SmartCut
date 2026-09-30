"""planejamento — o plano de CORTE (as decisões que vêm antes do motor).

Tudo aqui é puro: nenhuma consulta, nenhum encaixe, nenhum spyrrow. É o
caminho que roda antes de `services/nesting_v2` e que o motor só executa.

Módulos:
  * custo — quanto tempo cada risco de corte vai levar e qual perfil de tempo
    (Rápido / Equilibrado / Máximo) cabe no orçamento da Ordem de Corte
    (Configurações > Produção > "Tempo limite da ordem de corte (s)").

  * plano_corte — o plano de corte de um produto: quais riscos desenhar e
    quantas camadas de cada cor vão em cada um (enfesto multicor, CP-SAT).
    Ainda não está ligado ao fluxo de produção (Passo 3 do PC1).
  * estimador — comprimento e mesas de um risco pela área, sem motor.
"""

from services.planejamento.custo import (
    MULTIPLICADORES as MULTIPLICADORES,
    PERFIS as PERFIS,
    Orcamento as Orcamento,
    estimar_mesas as estimar_mesas,
    estimar_segundos as estimar_segundos,
)
