# M1-B — Motor v2 ajustado com base no diagnóstico M0-B

Tabela completa, moldes por mesa e conferência do espelho: `m1b/tabela.md`
(`m1b/resultados.json`, SVGs em `m1b/`). Reproduzir a partir de `backend/`:
`py -3.12 -m experimentos.nesting.comparar_m1b` (~8 min).

## O que mudou no v2 (`services/nesting_v2`)

- **Divisão mesa por mesa** (motor.py). Os moldes que não cabem duas vezes no
  comprimento (FRENTE/COSTAS ~99 cm em mesa de 150) enchem uma mesa por vez, e
  o spyrrow confirma se coube. Depois as peças pequenas vão para as folgas,
  começando pela mesa mais curta. O CP-SAT (`planejador.mochila`) propõe o lote,
  e o que passar do limite volta para a fila. No fim, cada mesa é reencaixada
  com mais tempo (polimento). A divisão CP-SAT em K mesas equilibradas do M1
  espalhava os cós e parava em 6,04 m; foi substituída.
- **Memória e tempo:** spyrrow com no máximo 2 workers (`MAX_WORKERS`), um por
  vez no processo (lock global), teto por chamada (2 s no enchimento, 6 s no
  polimento, 30 s na faixa sem limite) e teto brando de 600 s. O pico de
  memória volta em `Resultado.pico_memoria_mb`.
- **Pares:** na segunda cópia de `par`, o molde é espelhado sobre o eixo do fio
  (fio vertical → x, fio horizontal 90/270 → y) antes de ir para o spyrrow.
  `par_sem_espelho` continua com as duas cópias iguais. O placement sai com
  `"espelhada": true`.
- **Tabela por mesa:** `pecas_parte` do mapa_json lista os moldes da mesa
  (FRENTE G x1, COSTAS M x2). A grade por tamanho só aparece em
  `Resultado.resumo_enfesto()`.

## Aceite

| Critério | Resultado |
|---|---|
| PRETO 150 ≤ 6,01 m | **5,69 m / 5 mesas** ✅ |
| VERDE 150 ≤ 2,32 m | **1,98 m / 2 mesas** ✅ |
| Pares espelhados no SVG | cenário sintético (COSTAS como `par`): 12/12 metades conferem com o molde ou com o espelho, 0 erros; SVG com contorno tracejado e rótulo "(esp.)" ✅ |
| Tabela por mesa = moldes | ✅ (sem `pecas_por_tamanho` na mesa) |
| Memória | pico de 125–160 MB no v2 (B2: 290–360 MB) ✅ |

Ressalvas: rodada de 1 semente. Com 2 workers o spyrrow não é determinístico,
então os metros podem variar um pouco entre execuções.
