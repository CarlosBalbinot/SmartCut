# M0 — Diagnóstico e benchmark do motor de encaixe

Experimento fora do app. **Nenhum arquivo de produção foi alterado.** Os
motores externos rodam em processos separados; o motor atual é importado
direto do código de produção (`nesting_service._partes_do_enfesto` +
`nesting_bridge.executar`).

Resultado: `resultados/RELATORIO.md` (M0: tabela, recomendação, estimativa),
`resultados/RELATORIO_V2.md` (M1, histórico) e `resultados/RELATORIO_M1B.md`
(M1-B: motor v2 mesa por mesa, comparação atual).

## Arquivos

| Arquivo | O que faz |
|---|---|
| `exportar_pecas.py` | Lê o `smartcut.db` (somente leitura) e exporta as peças da OC-0002 como o motor atual as recebe → `dados/pedido000001_oc0002.json` |
| `comum.py` | Validação (sobreposição com shapely, largura, contagem, limite), métricas e SVG |
| `cand_a_atual.py` | Candidato A (código de produção, sem alteração) |
| `svgnest_headless.js` | SVGnest sem navegador, reaproveitando `backend/nesting/svgnest/util/*` |
| `motores.py` | Chamadas a SVGnest (Node), sparrow e lbf (Rust) |
| `estrategia_c.py` | Faixa única + corte (C1) e corte + reencaixe (C2) |
| `benchmark.py` | Roda tudo (3 sementes) → `resultados/` |
| `comparar_m1b.py` | M1-B: v1 × SVGnest corrigido (B2) × v2 (`services/nesting_v2`), limites 150/200/sem limite, um motor por vez em subprocesso com pico de memória → `resultados/m1b/` (substitui o `comparar_v1_v2.py` do M1) |

## Como reproduzir

```bash
cd backend
py -3.12 -m experimentos.nesting.exportar_pecas
# ambiente do experimento (shapely/pyclipper + deps do backend via system site-packages)
py -3.12 -m venv experimentos/nesting/.venv     # depois: include-system-site-packages = true
experimentos/nesting/.venv/Scripts/python.exe -m pip install shapely pyclipper
(cd experimentos/nesting && npm install)          # clipper-lib (só diagnóstico)
experimentos/nesting/.venv/Scripts/python.exe -m experimentos.nesting.benchmark   # ~40 min
# M1-B (só py -3.12 do sistema: spyrrow/ortools/shapely do requirements.txt + node_modules)
py -3.12 -m experimentos.nesting.comparar_m1b                                      # ~15 min
```

Ferramentas Rust (em `.tools/`, fora do git):

```bash
# rustup (host x86_64-pc-windows-gnu) com RUSTUP_HOME/CARGO_HOME em .tools/
# MinGW WinLibs (gcc 16.2 / binutils 2.47) — precisa ficar num caminho SEM espaços
git clone https://github.com/JeroenGar/sparrow  .tools/sparrow   && cargo build --release
git clone https://github.com/JeroenGar/jagua-rs .tools/jagua-rs  && cargo build --release -p lbf
```

## Versões testadas

| Ferramenta | Versão |
|---|---|
| Python | 3.12.10 (shapely 2.1.2, pyclipper 1.4.0, numpy 2.5.3) |
| Node.js | 24.15.0 |
| SVGnest | vendorizado em `backend/nesting/svgnest` (Jack Qiao, 2015), clipper.js 6.1.3a |
| clipper-lib (npm) | 6.4.2 (só para o diagnóstico do NFP) |
| Rust | rustc 1.98.1, x86_64-pc-windows-gnu |
| sparrow | 0.2.0, commit `7f0e10f` (2026-09-15), jagua-rs 0.8.3 |
| jagua-rs / lbf | jagua-rs 0.8.3 / lbf 0.0.1, commit `a037426` (2026-09-15) |
| spyrrow (binding Python do sparrow) | 0.9.0 (wheel cp312-win_amd64 no PyPI) — não usado no benchmark |
