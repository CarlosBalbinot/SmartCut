# M1-B — v1 × SVGnest corrigido (B2) × v2 (pedido 000001 / OC-0002)

Rodada rápida, 1 semente (B2 seed 1, 10 gerações; v2 seed 0, spyrrow com 2 workers). Um motor por vez, cada um num subprocesso; memória = pico do working set do subprocesso + pico do Node que ele abriu. Validação: sobreposição (shapely), largura, contagem e limite.

| Tecido | Limite | Motor | Metros | Mesas | Aprov. médio | Pior mesa | Tempo | Memória (pico) | Válido |
|---|---|---|---:|---:|---:|---:|---:|---:|:-:|
| PRETO | 150 cm | v1 atual | 9.11 | 9 | 49.3% | 34.1% | 1 s | 123 MB | sim |
| PRETO | 150 cm | SVGnest corrigido (B2) | 6.01 | 5 | 74.7% | 71.7% | 16 s | 342 MB | sim |
| PRETO | 150 cm | v2 sparrow + OR-Tools | 5.69 | 5 | 78.9% | 76.0% | 109 s | 159 MB | sim |
| PRETO | 200 cm | v1 atual | 6.28 | 4 | 71.5% | 66.1% | 0 s | 123 MB | sim |
| PRETO | 200 cm | SVGnest corrigido (B2) | 5.84 | 3 | 76.8% | 71.5% | 17 s | 337 MB | sim |
| PRETO | 200 cm | v2 sparrow + OR-Tools | 5.77 | 3 | 77.8% | 73.9% | 47 s | 139 MB | sim |
| PRETO | sem limite | v1 atual | 6.21 | 1 | 72.3% | 72.3% | 0 s | 123 MB | sim |
| PRETO | sem limite | SVGnest corrigido (B2) | 5.98 | 1 | 75.0% | 75.0% | 19 s | 342 MB | sim |
| PRETO | sem limite | v2 sparrow + OR-Tools | 5.34 | 1 | 84.1% | 84.1% | 31 s | 132 MB | sim |
| VERDE MILITAR | 150 cm | v1 atual | 3.44 | 3 | 46.4% | 40.1% | 0 s | 122 MB | sim |
| VERDE MILITAR | 150 cm | SVGnest corrigido (B2) | 2.32 | 2 | 68.7% | 61.1% | 5 s | 292 MB | sim |
| VERDE MILITAR | 150 cm | v2 sparrow + OR-Tools | 1.98 | 2 | 80.7% | 80.7% | 27 s | 134 MB | sim |
| VERDE MILITAR | 200 cm | v1 atual | 2.94 | 2 | 54.3% | 51.7% | 0 s | 122 MB | sim |
| VERDE MILITAR | 200 cm | SVGnest corrigido (B2) | 2.27 | 2 | 70.4% | 34.9% | 7 s | 357 MB | sim |
| VERDE MILITAR | 200 cm | v2 sparrow + OR-Tools | 1.94 | 1 | 82.3% | 82.3% | 9 s | 128 MB | sim |
| VERDE MILITAR | sem limite | v1 atual | 2.93 | 1 | 54.5% | 54.5% | 0 s | 121 MB | sim |
| VERDE MILITAR | sem limite | SVGnest corrigido (B2) | 1.98 | 1 | 80.7% | 80.7% | 6 s | 293 MB | sim |
| VERDE MILITAR | sem limite | v2 sparrow + OR-Tools | 1.94 | 1 | 82.4% | 82.4% | 32 s | 125 MB | sim |
| PRETO (COSTAS como par, sintético) | 150 cm | v2 sparrow + OR-Tools | 5.71 | 5 | 78.7% | 74.9% | 110 s | 160 MB | sim |

## Mesas do v2 (tabela por mesa = moldes)

### PRETO · 150 cm — 5 mesa(s), 5.69 m

Resumo do enfesto (grade por tamanho, peças por camada): G 15 · M 10 · P 5 · 1 camada(s)

| Mesa | Comprimento | Aprov. | Moldes que a mesa corta (por camada) | SVG |
|---:|---:|---:|---|---|
| 1 | 99.0 cm | 78.5% | COSTAS G x4 | `v2_preto_150_mesa1.svg` |
| 2 | 99.0 cm | 76.4% | COSTAS G x2, COSTAS M x2 | `v2_preto_150_mesa2.svg` |
| 3 | 117.8 cm | 76.0% | COSTAS M x2, COSTAS P x2, CÓS COSTAS G x1, CÓS FRENTE G x1, CÓS COSTAS P x1, CÓS FRENTE P x1 | `v2_preto_150_mesa3.svg` |
| 4 | 107.2 cm | 82.2% | FRENTE G x3 | `v2_preto_150_mesa4.svg` |
| 5 | 145.6 cm | 80.8% | FRENTE M x2, FRENTE P x1, CÓS COSTAS G x2, CÓS COSTAS M x2, CÓS FRENTE G x2, CÓS FRENTE M x2 | `v2_preto_150_mesa5.svg` |

### PRETO · 200 cm — 3 mesa(s), 5.77 m

Resumo do enfesto (grade por tamanho, peças por camada): G 15 · M 10 · P 5 · 1 camada(s)

| Mesa | Comprimento | Aprov. | Moldes que a mesa corta (por camada) | SVG |
|---:|---:|---:|---|---|
| 1 | 191.5 cm | 80.6% | FRENTE G x1, FRENTE M x2, COSTAS P x2, CÓS COSTAS M x2, CÓS FRENTE G x3, CÓS FRENTE M x2, CÓS FRENTE P x1 | `v2_preto_200_mesa1.svg` |
| 2 | 191.0 cm | 73.9% | FRENTE G x2, FRENTE P x1, COSTAS M x2, CÓS COSTAS G x3, CÓS COSTAS P x1 | `v2_preto_200_mesa2.svg` |
| 3 | 194.5 cm | 78.9% | COSTAS G x6, COSTAS M x2 | `v2_preto_200_mesa3.svg` |

### PRETO · sem limite — 1 mesa(s), 5.34 m

Resumo do enfesto (grade por tamanho, peças por camada): G 15 · M 10 · P 5 · 1 camada(s)

| Mesa | Comprimento | Aprov. | Moldes que a mesa corta (por camada) | SVG |
|---:|---:|---:|---|---|
| 1 | 533.7 cm | 84.1% | FRENTE G x3, FRENTE M x2, FRENTE P x1, COSTAS G x6, COSTAS M x4, COSTAS P x2, CÓS COSTAS G x3, CÓS COSTAS M x2, CÓS FRENTE G x3, CÓS COSTAS P x1, CÓS FRENTE M x2, CÓS FRENTE P x1 | `v2_preto_sem_limite_mesa1.svg` |

### VERDE MILITAR · 150 cm — 2 mesa(s), 1.98 m

Resumo do enfesto (grade por tamanho, peças por camada): G 5 · M 5 · 2 camada(s)

| Mesa | Comprimento | Aprov. | Moldes que a mesa corta (por camada) | SVG |
|---:|---:|---:|---|---|
| 1 | 99.0 cm | 80.7% | COSTAS G x2, COSTAS M x2 | `v2_verde_militar_150_mesa1.svg` |
| 2 | 98.6 cm | 80.7% | FRENTE G x1, FRENTE M x1, CÓS COSTAS G x1, CÓS COSTAS M x1, CÓS FRENTE G x1, CÓS FRENTE M x1 | `v2_verde_militar_150_mesa2.svg` |

### VERDE MILITAR · 200 cm — 1 mesa(s), 1.94 m

Resumo do enfesto (grade por tamanho, peças por camada): G 5 · M 5 · 2 camada(s)

| Mesa | Comprimento | Aprov. | Moldes que a mesa corta (por camada) | SVG |
|---:|---:|---:|---|---|
| 1 | 193.8 cm | 82.3% | FRENTE G x1, FRENTE M x1, COSTAS G x2, COSTAS M x2, CÓS COSTAS G x1, CÓS COSTAS M x1, CÓS FRENTE G x1, CÓS FRENTE M x1 | `v2_verde_militar_200_mesa1.svg` |

### VERDE MILITAR · sem limite — 1 mesa(s), 1.94 m

Resumo do enfesto (grade por tamanho, peças por camada): G 5 · M 5 · 2 camada(s)

| Mesa | Comprimento | Aprov. | Moldes que a mesa corta (por camada) | SVG |
|---:|---:|---:|---|---|
| 1 | 193.7 cm | 82.4% | FRENTE G x1, FRENTE M x1, COSTAS G x2, COSTAS M x2, CÓS COSTAS G x1, CÓS COSTAS M x1, CÓS FRENTE G x1, CÓS FRENTE M x1 | `v2_verde_militar_sem_limite_mesa1.svg` |

### PRETO (COSTAS como par, sintético) · 150 cm — 5 mesa(s), 5.71 m

Resumo do enfesto (grade por tamanho, peças por camada): G 15 · M 10 · P 5 · 1 camada(s)

| Mesa | Comprimento | Aprov. | Moldes que a mesa corta (por camada) | SVG |
|---:|---:|---:|---|---|
| 1 | 99.0 cm | 78.5% | COSTAS G x4 (2 esp.) | `v2_preto_par_espelhado_150_mesa1.svg` |
| 2 | 99.0 cm | 76.4% | COSTAS G x2 (1 esp.), COSTAS M x2 (1 esp.) | `v2_preto_par_espelhado_150_mesa2.svg` |
| 3 | 119.6 cm | 74.9% | COSTAS M x2 (1 esp.), COSTAS P x2 (1 esp.), CÓS COSTAS G x1, CÓS FRENTE G x1, CÓS COSTAS P x1, CÓS FRENTE P x1 | `v2_preto_par_espelhado_150_mesa3.svg` |
| 4 | 107.2 cm | 82.2% | FRENTE G x3 | `v2_preto_par_espelhado_150_mesa4.svg` |
| 5 | 145.6 cm | 80.8% | FRENTE M x2, FRENTE P x1, CÓS COSTAS G x2, CÓS COSTAS M x2, CÓS FRENTE G x2, CÓS FRENTE M x2 | `v2_preto_par_espelhado_150_mesa5.svg` |

## Conferência do espelho (PRETO (COSTAS como par, sintético))

12 de 12 peças de `par` conferem com o molde (normal) ou com o espelho sobre o fio (espelhada); erros: 0.
