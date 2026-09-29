# v1 × v2 — pedido 000001 / OC-0002

- v1 = motor atual (nest_worker.js por bounding box + divisão gulosa).
- v2 = spyrrow (strip packing, polígono real) + OR-Tools CP-SAT na divisão.
- Espaçamento entre peças = 0. Fio vertical → só 0°/180°. Encolhimento 0%.
- Os dois v2 de PRETO 150 são duas rodadas iguais, para medir determinismo.

| Tecido | Motor | Limite | Mesas | Metros totais | Aprov. médio | Pior mesa | Tempo | Válido |
|---|---|---:|---:|---:|---:|---:|---:|:-:|
| PRETO | v1 (atual) | 150 | 9 | 9.11 | 49.3% | 34.1% | 0.8 | sim |
| PRETO | v2 (spyrrow+CP-SAT) — rodada A | 150 | 5 | 6.04 | 74.2% | 67.3% | 422.6 | sim |
| PRETO | v2 (spyrrow+CP-SAT) — rodada B | 150 | 5 | 6.04 | 74.2% | 67.3% | 428.5 | sim |
| PRETO | v1 (atual) | 800 | 1 | 6.21 | 72.3% | 72.3% | 0.2 | sim |
| PRETO | v2 (spyrrow+CP-SAT) | 800 | 1 | 5.35 | 83.8% | 83.8% | 60.4 | sim |
| VERDE MILITAR | v1 (atual) | 150 | 3 | 3.44 | 46.4% | 40.1% | 0.5 | sim |
| VERDE MILITAR | v2 (spyrrow+CP-SAT) | 150 | 2 | 2.22 | 71.9% | 71.5% | 58.7 | sim |
| VERDE MILITAR | v1 (atual) | 800 | 1 | 2.93 | 54.5% | 54.5% | 0.1 | sim |
| VERDE MILITAR | v2 (spyrrow+CP-SAT) | 800 | 1 | 1.94 | 82.4% | 82.4% | 61.7 | sim |

## Mesas do v2

- **PRETO · 150 cm · limite 150** (rodada A) — mesa 1: 133 cm, 4 peças · Gx1, Px3; mesa 2: 106 cm, 8 peças · Gx5, Px1, Mx2; mesa 3: 121 cm, 7 peças · Gx4, Mx2, Px1; mesa 4: 124 cm, 4 peças · Gx2, Mx2; mesa 5: 120 cm, 7 peças · Gx3, Mx4
- **PRETO · 150 cm · limite 800** — mesa 1: 535 cm, 30 peças · Gx15, Mx10, Px5
- **VERDE MILITAR · 142 cm · limite 150** — mesa 1: 111 cm, 5 peças · Mx2, Gx3; mesa 2: 111 cm, 5 peças · Gx2, Mx3
- **VERDE MILITAR · 142 cm · limite 800** — mesa 1: 194 cm, 10 peças · Gx5, Mx5

## Determinismo

- PRETO 150 rodado 2× com 120 s de passada (24 s por mesa no K final): comprimentos [133.5, 106.0, 120.6, 124.3, 120.0] / [133.5, 106.0, 120.6, 124.3, 120.0] — idêntico (determinístico).
