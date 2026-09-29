"""Benchmark M0 — motores de encaixe no pedido 000001 / OC-0002.

Uso (a partir de backend/):
    experimentos/nesting/.venv/Scripts/python.exe -m experimentos.nesting.benchmark [--rapido]

Gera em resultados/: um SVG por candidato × tecido (melhor semente),
resultados.json (todas as execuções) e tabela.md.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

from . import cand_a_atual, comum, motores
from .estrategia_c import c1_corte_unico, c2_corte_reencaixe

LIM = comum.LIMITE_CM
RAPIDO = "--rapido" in sys.argv
SEEDS = [1] if RAPIDO else [1, 2, 3]
T_SPARROW = 10 if RAPIDO else 60  # s — faixa única
T_SPARROW_C2 = 5 if RAPIDO else 20  # s — cada faixa do reencaixe
T_SVGNEST = 10 if RAPIDO else 90  # s
SVG_OK = {"curveTolerance": 0.1, "inflate": 0.1, "sanearNfp": True}



def candidatos(tec: dict, seed: int) -> dict[str, tuple[list[list[dict]], float, float | None]]:
    """{nome: (partes, segundos, limite_para_validar)} para uma semente."""
    W = tec["largura_cm"]
    pecas = tec["pecas"]
    # Pares: só o motor atual (A) força as duas cópias na mesma parte; aqui
    # ficam livres e a coluna "pares divididos" mostra quantos separaram.
    pares: set[str] = set()
    out: dict = {}

    if seed == SEEDS[0]:  # determinístico
        partes, s, _ = cand_a_atual.rodar(tec, None)
        out["A0 atual, sem limite (antes)"] = (partes, s, None)
        partes, s, _ = cand_a_atual.rodar(tec, LIM)
        out["A  atual + divisão gulosa"] = (partes, s, LIM)

    # B — SVGnest com polígono real, várias mesas de 150 cm.
    # B1 "de fábrica": config padrão do svgnest.js (curveTolerance 0,3, sem
    # correção do NFP) — mede o que o SVGnest entrega sem ajustes.
    partes, info = motores.svgnest(pecas, W, LIM, generations=10, seed=seed, sanearNfp=False)
    out["B1 SVGnest de fábrica, 10 gerações"] = ([comum.normalizar_parte(p) for p in partes], info["seconds"], LIM)
    # B2/B3 corrigido: NFP saneado + contorno simplificado a 0,1 cm e inflado 0,1 cm
    partes, info = motores.svgnest(pecas, W, LIM, generations=10, seed=seed, **SVG_OK)
    out["B2 SVGnest corrigido, 10 gerações"] = ([comum.normalizar_parte(p) for p in partes], info["seconds"], LIM)
    partes, info = motores.svgnest(pecas, W, LIM, timeLimitSec=T_SVGNEST, seed=seed, **SVG_OK)
    out[f"B3 SVGnest corrigido, {T_SVGNEST}s"] = ([comum.normalizar_parte(p) for p in partes], info["seconds"], LIM)

    # C com SVGnest como motor de faixa (uma mesa bem longa)
    t0 = time.perf_counter()
    faixa_svg, _ = motores.svgnest(pecas, W, 5000, timeLimitSec=T_SVGNEST, seed=seed, **SVG_OK)
    faixa_svg = faixa_svg[0]
    s_faixa = time.perf_counter() - t0
    out[f"B4 SVGnest corrigido faixa única, {T_SVGNEST}s (sem limite)"] = ([comum.normalizar_parte(faixa_svg)], s_faixa, None)
    t0 = time.perf_counter()
    partes = c1_corte_unico(pecas, lambda _: faixa_svg, LIM, pares)
    out["C1 faixa SVGnest + corte"] = (partes, s_faixa + time.perf_counter() - t0, LIM)

    # D — sparrow (strip packing) + estratégia C
    t0 = time.perf_counter()
    faixa_sp, _ = motores.sparrow(pecas, W, T_SPARROW, seed=seed)
    s_faixa = time.perf_counter() - t0
    out[f"D0 sparrow faixa única, {T_SPARROW}s (sem limite)"] = ([comum.normalizar_parte(faixa_sp)], s_faixa, None)
    t0 = time.perf_counter()
    partes = c1_corte_unico(pecas, lambda _: faixa_sp, LIM, pares)
    out["C1 faixa sparrow + corte"] = (partes, s_faixa + time.perf_counter() - t0, LIM)

    t0 = time.perf_counter()
    partes = c2_corte_reencaixe(pecas, lambda lote: motores.sparrow(lote, W, T_SPARROW_C2, seed=seed)[0], LIM, pares)
    out[f"C2 sparrow + corte + reencaixe ({T_SPARROW_C2}s/faixa)"] = (partes, time.perf_counter() - t0, LIM)

    # D — jagua-rs lbf em modo bin packing (várias mesas)
    if motores.LBF.exists():
        partes, info = motores.lbf_bpp(pecas, W, LIM, seed=seed)
        out["D2 jagua-rs lbf, várias mesas (BPP)"] = ([comum.normalizar_parte(p) for p in partes], info["segundos"], LIM)
    return out


def main() -> None:
    dados = comum.carregar()
    comum.RESULTADOS.mkdir(exist_ok=True)
    todos: dict = {}
    for tec in dados["tecidos"]:
        cor = tec["cor"]
        todos[cor] = {"limite_inferior": comum.limite_inferior(tec), "largura_cm": tec["largura_cm"], "camadas": tec["camadas"], "candidatos": {}}
        runs: dict[str, list] = {}
        for seed in SEEDS:
            for nome, (partes, seg, lim) in candidatos(tec, seed).items():
                m = comum.metricas(tec, partes, seg, lim)
                m["seed"] = seed
                runs.setdefault(nome, []).append((m, partes))
                print(f"{cor:14} s{seed} {nome:48} {m['metros']:6.2f} m {m['partes']:2} p "
                      f"{m['aproveitamento_medio'] * 100:5.1f}% pior {m['aproveitamento_pior'] * 100:5.1f}% "
                      f"{m['segundos']:6.1f}s {'ok' if m['valido'] else m['problemas'][:2]}", flush=True)
        for nome, lst in runs.items():
            validos = [x for x in lst if x[0]["valido"]] or lst
            melhor, partes = min(validos, key=lambda x: x[0]["metros"])
            slug = nome.split()[0] + "_" + cor.replace(" ", "_").lower()
            comum.svg(tec, partes, melhor, f"{nome} — {tec['tecido']} ({tec['largura_cm']:g} cm, seed {melhor['seed']})",
                      comum.RESULTADOS / f"{slug}.svg")
            todos[cor]["candidatos"][nome] = {
                "melhor": melhor,
                "metros_por_seed": [x[0]["metros"] for x in lst],
                "metros_mediana": statistics.median(x[0]["metros"] for x in lst),
                "segundos_medio": round(statistics.mean(x[0]["segundos"] for x in lst), 1),
                "svg": f"{slug}.svg",
            }

    (comum.RESULTADOS / "resultados.json").write_text(json.dumps(todos, ensure_ascii=False, indent=1), encoding="utf-8")
    linhas = ["| Candidato | Tecido | Metros (melhor) | Metros (mediana) | Partes | Aprov. médio | Pior parte | Tempo (s) | Válido | Pares divididos |",
              "|---|---|---:|---:|---:|---:|---:|---:|:-:|---:|"]
    for cor, r in todos.items():
        for nome, c in r["candidatos"].items():
            m = c["melhor"]
            linhas.append(
                f"| {nome} | {cor} | {m['metros']:.2f} | {c['metros_mediana']:.2f} | {m['partes']} | "
                f"{m['aproveitamento_medio'] * 100:.1f}% | {m['aproveitamento_pior'] * 100:.1f}% | {c['segundos_medio']:.1f} | "
                f"{'sim' if m['valido'] else 'NÃO'} | {m['pares_divididos']} |"
            )
    (comum.RESULTADOS / "tabela.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print("\n".join(linhas))


if __name__ == "__main__":
    main()
