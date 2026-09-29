# M0 — Relatório (pedido 000001 / OC-0002)

> **Status: parcial.** A rodada completa (3 sementes, 60–90 s por motor) foi
> interrompida pelo sistema por falta de memória. Os números abaixo vêm da
> rodada rápida (1 semente, 5–10 s por motor) e das execuções avulsas de
> SVGnest feitas depois da correção do NFP. Todos passaram no validador
> (polígono ORIGINAL, sem sobreposição > 1 cm², dentro da largura, contagem
> exata, partes ≤ 150 cm).
> Para refazer: `python -m experimentos.nesting.benchmark` (a partir de backend/).

## Casos

| Tecido | Largura | Camadas | Conjuntos/camada | Peças | Área | 100% de aproveitamento | Mín. de mesas |
|---|---:|---:|---|---:|---:|---:|---:|
| PRETO | 150 cm | 1 | P1 M2 G3 | 30 | 6,73 m² | 4,49 m | 3 |
| VERDE MILITAR | 142 cm | 2 | M1 G1 | 10 | 2,27 m² | 1,60 m | 2 |

Espaçamento entre peças = 0 (igual ao motor atual). Fio vertical → só 0°/180°.
Encolhimento dos dois lotes = 0%, então metros = comprimento do risco (uma camada).

## Tabela comparativa

| Candidato | Tecido | Metros | Partes | Aprov. médio | Pior parte | Tempo | Válido | Pares divididos |
|---|---|---:|---:|---:|---:|---:|:-:|---:|
| A0 atual, sem limite (referência "antes") | PRETO | 6,21 | 1 | 72,3% | 72,3% | 0,4 s | sim | 0 |
| **A atual + divisão gulosa (hoje)** | PRETO | **9,11** | **9** | 49,3% | **34,1%** | 0,8 s | sim | 0 |
| B1 SVGnest de fábrica (curveTol 0,3), 10 ger. | PRETO | 6,03 | 5 | — | — | 6 s | **NÃO** (51–77 cm² de sobreposição por parte) | — |
| B2 SVGnest corrigido, 10 ger. | PRETO | 6,01 | 5 | 74,7% | não medido | 30 s | sim | — |
| D0 sparrow, faixa única, 10 s (sem limite) | PRETO | 5,57 | 1 | 80,5% | — | 10 s | sim | — |
| C1 faixa sparrow + corte | PRETO | 6,51 | 6 | 68,9% | 55,7% | 11 s | sim | livre |
| C2 sparrow + corte + reencaixe (5 s/faixa) | PRETO | 6,73 | 6 | 66,7% | 54,1% | 27 s | sim | livre |
| D2 jagua-rs lbf, várias mesas (BPP) | PRETO | 6,67 | 6 | 67,3% | 18,4% | 0,2 s | sim | livre |
| A0 atual, sem limite (referência "antes") | VERDE | 2,93 | 1 | 54,5% | 54,5% | 0,1 s | sim | 0 |
| **A atual + divisão gulosa (hoje)** | VERDE | **3,44** | **3** | 46,4% | 40,1% | 0,2 s | sim | 0 |
| B1 SVGnest de fábrica, 10 ger. | VERDE | 2,26 | 2 | — | — | 1,5 s | **NÃO** (18 cm²) | — |
| B2 SVGnest corrigido, 10 ger. | VERDE | 2,32 | 2 | 68,7% | não medido | 10 s | sim | — |
| D0 sparrow, faixa única, 10 s (sem limite) | VERDE | 1,94 | 1 | 82,3% | — | 10 s | sim | — |
| C1 faixa sparrow + corte | VERDE | 2,36 | 2 | 67,5% | 64,6% | 11 s | sim | livre |
| C2 sparrow + corte + reencaixe | VERDE | 2,36 | 2 | 67,6% | 64,6% | 6 s | sim | livre |
| D2 jagua-rs lbf, várias mesas (BPP) | VERDE | 2,26 | 2 | 70,7% | 60,0% | 0,1 s | sim | livre |

"livre" = só o A força as duas cópias do par na mesma parte; nos outros a
coluna ainda não foi consolidada (é medida por `comum.validar`).
E (libnest2d/pynest2d): não testado — ver licenças.

SVGs em `resultados/` (A0, A, C1 = sparrow, C2, D0, D2). Os SVGs de B foram
apagados porque eram anteriores à correção do NFP; saem de novo na rodada completa.

## Licenças e distribuição

| Motor | Licença | Uso comercial/SaaS | Distribuição no Windows | Offline |
|---|---|---|---|---|
| nest_worker.js (atual) | próprio | sim | Node do sistema (`node` no PATH) | sim |
| SVGnest | MIT (clipper.js: Boost) | sim | JS puro, mesmo Node do worker | sim |
| sparrow | MIT | sim | exe estático de 2,7 MB (build Rust) **ou** `spyrrow` 0.9.0 (MIT, wheel cp312-win_amd64 no PyPI) | sim |
| jagua-rs / lbf | MPL-2.0 (copyleft por arquivo: só é preciso publicar alterações feitas nos arquivos dele) | sim | exe (build Rust) | sim |
| libnest2d / pynest2d | LGPL-3.0 | sim, com linkagem dinâmica | sem wheel no PyPI; build C++ (boost, nlopt, clipper) via conan | sim |

## Diagnóstico do motor atual

- **Não é o SVGnest.** `nesting_bridge.executar` chama `nest_worker.js`, um empacotador
  *skyline bottom-left* por **bounding box**. O SVGnest em `backend/nesting/svgnest/` só é
  empacotado (`smartcut.spec`), nunca executado.
- **Parâmetros:** não há população, iterações, espaçamento nem curveTolerance. Ordena por área
  (maior primeiro) e escolhe a rotação com menor topo. Único limite: `NESTING_TIMEOUT_SEC=120`.
  `bin.height` é ignorado.
- **Fio → rotações** (`_rotacoes`): vertical 0/180, horizontal 90/270, 45graus 45/135/225/315,
  sem fio 0/90/180/270. Com bounding box, 180° é igual a 0° (não ajuda em nada) e 45° piora
  (o bbox cresce). `rotacao_base` é aplicada antes, no Python, em torno do centro do bbox.
  Cadastro atual: 16 moldes, todos com fio vertical.
- **Pares:** `par` e `par_sem_espelho` viram 2 cópias **iguais** (`_MULT`). O `par` **não é
  espelhado** (bug latente; nesta OC só existe `par_sem_espelho`). A divisão mantém as duas
  cópias na mesma parte (`_fechar_pares`).
- **Divisão (N1)** `_partes_do_enfesto`: encaixa tudo, a parte fica com as peças cujo topo é
  ≤ 150, e o resto é reencaixado do zero. É gulosa: o skyline empilha as peças grandes primeiro,
  cada parte acaba com uma "fileira" e as pequenas vão sobrando para o fim (a parte 9 do PRETO
  tem 19 cm, só com dois CÓS).
- **Limite estrutural do caso:** FRENTE/COSTAS têm 95–99 cm. Numa mesa de 150 só cabe
  uma fileira delas, mais uma faixa de ~51 cm para os cós. Por isso qualquer motor perde para a
  faixa única (sparrow, sem limite: 5,57 m; melhor resultado com limite: ~6,0 m).
- **SVGnest vendorizado tem defeito com polígono real:** a simplificação (curveTolerance 0,3)
  corta as curvas por dentro, e o `MinkowskiSum` devolve NFP auto-intersectante (medi 12 cm² de
  penetração no COSTAS M 0°×180°; o clipper-lib 6.4.2 dá o mesmo). O resultado são peças
  sobrepostas. Correção usada no B2: sanear o NFP (`SimplifyPolygon` NonZero), tolerância de
  0,1 cm e inflar o contorno em 0,1 cm.

## Recomendação

1. **Motor:** sparrow via **spyrrow** (MIT, wheel Windows cp312, roda offline, dentro do processo
   Python, sem Node e sem Rust na máquina do cliente). Usa polígono real, `allowed_orientations`
   e `min_items_separation`. Foi o de maior densidade medida: 80–82% na faixa, contra 54–72% hoje.
2. **Divisão:** não usar "faixa + corte" (C1/C2). Com peças de ~99 cm em mesa de 150 ele
   perdeu para o empacotamento por mesa (PRETO: C 6,5–6,7 m/6 partes; SVGnest por mesa
   6,01 m/5 partes). O sparrow só faz faixa (não tem bin packing), então a divisão tem de encher
   **uma mesa por vez**: escolher um subconjunto (maiores primeiro, alvo ≈ área da mesa ×
   densidade), rodar o spyrrow com tempo curto, aceitar se a faixa for ≤ 150 cm e, se passar,
   tirar a peça menor. Essa estratégia **ainda não foi medida**. O único resultado medido que
   serve de base é o SVGnest corrigido por mesa. Refazer a rodada completa antes de decidir.
3. Espelhar a segunda cópia de `par` (hoje é um bug).

## Estimativa de integração

| Arquivo | Mudança |
|---|---|
| `services/nesting_service.py` | trocar `executar`/`_partes_do_enfesto` pelo novo motor e pela nova divisão; espelhar `par`; `pecas_por_tamanho` por parte |
| `nesting/nesting_bridge.py`, `nesting/nest_worker.js` | aposentar (ou manter como fallback) |
| `services/nesting_v2/` | **já existe, criado nesta tarde fora desta sessão** (spyrrow). Encaixar a estratégia de mesa ali |
| `requirements.txt`, `smartcut.spec` | `spyrrow`, e hiddenimport/binário do .pyd no PyInstaller |
| `frontend/src/pages/OrdemCorteDetalhePage.jsx` | tabela por parte a partir de `pecas_parte` |
| `services/relatorios/dados_ordem_corte.py`, `relatorios/producao/relPro001.html` | idem, e totais sem repetir o enfesto |
| `services/ordem_corte_service.py` | totais (já deduplicam por enfesto; revisar se o campo mudar) |
| `tests/` | contagem por parte, pares espelhados, limite, sem sobreposição (shapely) |

Na ordem de 1 a 2 dias de backend, mais ~½ dia de front/relatório/testes. O contrato do
placement (x, y do bbox + rotação) é mantido, então Visualizador e PDF não mudam.

## Causa do bug da tabela por parte

`nesting_service._gerar_para_tecido` monta `extras["pecas_por_tamanho"] =
linhas_enfesto(enfesto, …)`, que é o **enfesto inteiro** (linha 281), e copia esse `extras` em
cada parte (`extras_parte = {**extras, …}`, linhas 309–315). O que cada parte corta de verdade
está em `pecas_parte` (linha 314), mas a tela (`OrdemCorteDetalhePage.jsx:896`) e o relatório de
produção (`dados_ordem_corte.py:221`) leem `pecas_por_tamanho`. Resultado: P1 M2 G3 em todas as
9 partes, e no relatório `pecas_por_camada`/`pecas_total` somam o enfesto 9 vezes.
Detalhe para a correção: `pecas_parte` é por **molde** (FRENTE G, COSTAS G…), não por peça
de roupa. Uma parte pode ter a FRENTE de um G e não as COSTAS, então a tabela da parte tem de
listar moldes.
