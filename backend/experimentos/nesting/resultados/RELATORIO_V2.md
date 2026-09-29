# v1 × v2 — Motor de encaixe v2 embutido (relatório final)

> **Status: completo.** Motor v2 (spyrrow + OR-Tools CP-SAT, backend puro) convive
> com o v1 (SVGnest via bridge, intacto) e ganha nos dois critérios de aceite
> nos cenários com limite de mesa: **menos metros E menos mesas que o v1**.

## Resultados (pedido 000001 / OC-0002)

| Tecido | Motor | Limite | Mesas | Metros totais | Aprov. médio | Pior mesa | Tempo | Válido |
|---|---:|---:|---:|---:|---:|---:|:-:|
| PRETO | v1 (atual) | 150 | 9 | 9,11 | 49,3% | 34,1% | 0,8 s | sim |
| PRETO | **v2** (rodada A=B) | 150 | **5** | **6,04** | 74,2% | 67,3% | ~7 min | sim |
| PRETO | v1 (atual) | 800 | 1 | 6,21 | 72,3% | 72,3% | 0,2 s | sim |
| PRETO | **v2** | 800 | 1 | **5,35** | 83,8% | 83,8% | 60 s | sim |
| VERDE MILITAR | v1 (atual) | 150 | 3 | 3,44 | 46,4% | 40,1% | 0,5 s | sim |
| VERDE MILITAR | **v2** | 150 | **2** | **2,22** | 71,9% | 71,5% | 59 s | sim |
| VERDE MILITAR | v1 (atual) | 800 | 1 | 2,93 | 54,5% | 54,5% | 0,1 s | sim |
| VERDE MILITAR | **v2** | 800 | 1 | **1,94** | 82,4% | 82,4% | 62 s | sim |

Aceite:
- PRETO@150: **5 mesas < 9** e **6,04 m < 9,11 m** ✅ (nenhuma mesa passa de 150 cm; máx 133,5 cm)
- VERDE@150: **2 mesas < 3** e **2,22 m < 3,44 m** ✅ (máx 111 cm)
- Determinismo: PRETO@150 rodado 2× (120 s/passada, 24 s/mesa no K final) → idêntico ✅
- v1 intacto: `pytest` 124 passed ✅

## Robustez multi-seed (semente do CP-SAT + spyrrow)

Mesmos cenários com seeds 0, 1, 2 (orçamento de 60 s/passada, igual ao benchmark);
a seed 0 reproduz exatamente o benchmark (consistência ponta a ponta):

| Tecido | seed | Mesas | Comprimentos (cm) | Metros | Aprov. | Válido |
|---|---|---|---:|---:|---:|:-:|
| PRETO | 0 | 5 | 133.5, 106.0, 120.6, 124.3, 120.0 | 6,044 | 74,2% | sim |
| PRETO | 1 | 5 | 133.5, 120.6, 122.0, 123.9, 117.6 | 6,176 | 72,7% | sim |
| PRETO | 2 | 5 | 123.9, 133.5, 120.6, 121.9, 117.6 | 6,175 | 72,7% | sim |
| VERDE MILITAR | 0 | 2 | 110.5, 111.4 | 2,220 | 71,9% | sim |
| VERDE MILITAR | 1 | 2 | 111.4, 110.6 | 2,219 | 71,9% | sim |
| VERDE MILITAR | 2 | 2 | 111.4, 110.6 | 2,220 | 71,9% | sim |

O nº de mesas é invariante (5 e 2) e os metros variam < 0,14 m entre seeds — o
resultado não depende da semente. Seeds diferentes geram partições
equilibradas diferentes (fazem parte dos comprimentos trocarem de posição),
todas válidas e dentro do limite.

## Arquitetura do v2 (`backend/services/nesting_v2/`)

1. **PREPARAÇÃO** (`geometria.py`) — molde → `Unidade` de corte (polígono real,
   `rotacoes` pelo sentido do fio, par espelhado como item próprio; `quantidade`
   já é o total físico).
2. **PLANEJAMENTO** (`planejador.py`) — CP-SAT divide as unidades em K mesas;
   capacidade = largura × limite × `densidade_alvo` (0,80) e **objetivo makespan**
   (minimizar a carga máxima por mesa).
3. **ENCAIXE** (`encaixador.py`) — spyrrow em cada mesa (`strip_height` = largura
   útil, `early_termination=True`), minimizando o comprimento.
4. **AJUSTE** (`motor.py`) — mesa acima do limite: as peças excedentes não voltam
   para a mesma mesa (restrição `proibidas`) e tudo é re-planejado; máximo
   `ciclos_max` por tentativa, orçamento de spyrrow resetado por passada.
5. **SAÍDA** — `mapa_json` no mesmo formato do v1, com `pecas_por_tamanho` DA MESA
   (corrige o bug do v1 que repetia a linha do enfesto em todas as partes) — ver
   apêndice "Mesas do v2" em `tabela_v1_v2.md`.

### Diagnóstico que decidiu o objetivo (makespan)

A primeira versão do CP-SAT era de factibilidade pura: o solver devolvia a
primeira partição, que na prática era gulosa — empilhava 16–18 mil cm² numa mesa
(que nunca cabe no limite) e deixava outras quase vazias. Mesmo K=6 (cada mesa
com só 2–3 peças grandes) falhava, e a escalada chegava a 12 mesas. Com
`Minimize(max(carga))` a partição equilibra as mesas por área em milissegundos e
o spyrrow fecha cada mesa no limite — o PRETO@150 pousa em **K=5** no ciclo 1.

## PyInstaller (verificação, sem correção)

O `backend/smartcut.spec` atual já inclui `shapely`; o executável
`backend/dist/smartcut-backend.exe` tem 54,43 MB. Para o v2 no empacotamento
faltariam os novOs pacotes:

- `services.nesting_v2` — módulo próprio (passar a incluir).
- `spyrrow` ~1,2 MB — precisa `collect_all` (dados/recursos).
- `ortools` ~80,9 MB instalados — pesado; `collect_all` recomendado (tem dados
  binários internos e subpacotes com imports dinâmicos).

O executável cresceria ~80–90 MB (→ ~135–145 MB). Nada foi alterado no spec nem
no exe: ficou registrado como pendência de empacotamento, fora deste objetivo.

## Como reproduzir (a partir de `backend/`)

```powershell
py -3.12 -m pytest                                  # suíte (124 testes, v1 intacto)
py -3.12 -m ruff check services/nesting_v2 experimentos/nesting/comparar_v1_v2.py
py -3.12 -m experimentos.nesting.comparar_v1_v2     # benchmark completo (~25 min)
```

SVGs dos riscos em `resultados/v1_*.svg` e `resultados/v2_*.svg`.