"""comparar_v1_v2.py — motor v1 (SVGnest via bridge) contra motor v2.

Como o v2 é embutido (spyrrow + OR-Tools CP-SAT, sem Node), ele roda neste
mesmo processo Python; o v1 é importado de `cand_a_atual` (código de produção,
sem alteração), como no benchmark M0.

Casos: pedido 000001 / OC-0002 —
  PRETO (P1 M2 G3 por camada, 150 cm) e VERDE MILITAR (M1 G1 por camada,
  142 cm), limites 150 e 800.

Saída: tabela `motor | limite | mesas | metros totais | aproveitamento médio |
pior mesa | tempo` em resultados/tabela_v1_v2.md, e um SVG por motor × caso em
resultados/.

Roda a dois passos do v2 para o PETO com limite 150 para medir determinismo:
execuções idênticas são esperadas quando cada mesa tem orçamento suficiente
para o spyrrow convergir (com early_termination=True o resultado estabiliza).

Uso: a partir de backend/:
  py -3.12 -m experimentos.nesting.comparar_v1_v2
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from experimentos.nesting import cand_a_atual  # noqa: E402
from experimentos.nesting.comum import RESULTADOS, carregar, comprimento, metricas, svg  # noqa: E402
from services.nesting_v2 import gerar  # noqa: E402
from services.nesting_v2.geometria import Peca  # noqa: E402

LIMITES = (150.0, 800.0)
# Orçamento de spyrrow por passada (K mesas): cada mesa recebe ORCAMENTO_V2/K.
ORCAMENTO_V2 = 60.0
# PRETO 150 vai com 120 s/passada (24 s por mesa no K final) para o spyrrow
# convergir nas duas rodadas e o teste de determinismo medir de verdade.
ORCAMENTO_DETERMINISMO = 120.0


def _pecas_v2(tec: dict) -> list[Peca]:
    return [
        Peca(
            id=p["id"],
            poligono=p["polygon"],
            quantidade=p["quantity"],
            rotacoes=tuple(float(r) for r in p["rotations"]),
            tipo_corte=p["tipo_corte"],
            peca=p.get("peca"),
            tamanho=p.get("tamanho"),
            grupo_nome=p.get("grupo_nome"),
        )
        for p in tec["pecas"]
        if p["quantity"] > 0
    ]


def _partes_v2(mesas) -> list[list[dict]]:
    """Mesas do v2 no formato do comum.py (id / rotation / points) — o mesmo
    contrato do v1: R(rotation)·poligono ancorado pelo bbox em (x, y)."""
    return [
        [
            {
                "id": pl["id"],
                "rotation": pl["rotation"],
                "points": cand_a_atual._pontos(pl["polygon"], pl["rotation"], pl["x"], pl["y"]),
            }
            for pl in mesa.pecas
        ]
        for mesa in mesas
    ]


def _rodar_v1(tec: dict, limite: float) -> tuple[list[list[dict]], float, list[float]]:
    partes, seg, motor = cand_a_atual.rodar(tec, limite)
    return partes, seg, [len(p) for p in partes]


def _rodar_v2(tec: dict, limite: float, orcamento: float) -> tuple[list[list[dict]], float, list[float], list]:
    t0 = time.perf_counter()
    mesas = gerar(
        _pecas_v2(tec),
        tec["largura_cm"],
        limite,
        camadas=tec["camadas"],
        tempo_limite_s=orcamento,
        seed=0,
    )
    seg = time.perf_counter() - t0
    return _partes_v2(mesas), seg, [len(m.pecas) for m in mesas], mesas


def _linha(tec: dict, motor: str, limite: float, partes, seg) -> str:
    m = metricas(tec, partes, seg, limite)
    val = "sim" if m["valido"] else "NÃO: " + "; ".join(m["problemas"][:2])
    return (
        f"| {tec['cor']} | {motor} | {limite:g} | {m['partes']} | {m['metros']:.2f} | "
        f"{m['aproveitamento_medio'] * 100:.1f}% | {m['aproveitamento_pior'] * 100:.1f}% | "
        f"{m['segundos']:.1f} | {val} |"
    )


def _detalhe_mesas(partes: list[list[dict]], mesas: list | None = None) -> str:
    """Tabela por mesa (comprimento, nº de peças e tamanhos), sem repetir nada."""
    itens: list[str] = []
    for i, p in enumerate(partes, start=1):
        base = f"mesa {i}: {comprimento(p):.0f} cm, {len(p)} peças"
        if mesas is not None and i <= len(mesas):
            tam = mesas[i - 1].pecas_por_tamanho
            resumo = ", ".join(f"{e.get('grupo_nome') or ''} {e['tamanho'] or ''}x{e['pecas']}".strip() for e in tam)
            base += f" · {resumo}"
        itens.append(base)
    return "; ".join(itens)


def main() -> None:
    # Console do Windows é cp1252 e o markdown tem caracteres fora dele (→, ²);
    # o print final não pode derrubar o script depois do benchmark pronto.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass
    dados = carregar()
    linhas: list[str] = []
    detalhes: list[str] = []
    mesas_v2: list[str] = []
    for tec in dados["tecidos"]:
        tec_id = "preto" if tec["cor"] == "PRETO" else "verde_militar"
        for limite in LIMITES:
            nome = f"{tec['cor']} · {tec['largura_cm']:g} cm · limite {limite:g}"

            partes_v1, seg_v1, _ = _rodar_v1(tec, limite)
            m1 = metricas(tec, partes_v1, seg_v1, limite)
            linhas.append(_linha(tec, "v1 (atual)", limite, partes_v1, seg_v1))
            svg(tec, partes_v1, m1, f"v1 — {nome}", RESULTADOS / f"v1_{tec_id}_{int(limite)}.svg")

            if tec["cor"] == "PRETO" and limite == 150.0:
                # duas rodadas com orçamento de convergência, para o determinismo
                partes_a, seg_a, _, mesas_a = _rodar_v2(tec, limite, ORCAMENTO_DETERMINISMO)
                partes_b, seg_b, _, mesas_b = _rodar_v2(tec, limite, ORCAMENTO_DETERMINISMO)
                ma = metricas(tec, partes_a, seg_a, limite)
                mb = metricas(tec, partes_b, seg_b, limite)
                linhas.append(_linha(tec, "v2 (spyrrow+CP-SAT) — rodada A", limite, partes_a, seg_a))
                linhas.append(_linha(tec, "v2 (spyrrow+CP-SAT) — rodada B", limite, partes_b, seg_b))
                svg(tec, partes_a, ma, f"v2 — {nome}", RESULTADOS / f"v2_{tec_id}_{int(limite)}.svg")
                mesas_v2.append(f"- **{nome}** (rodada A) — {_detalhe_mesas(partes_a, mesas_a)}")
                igual = (
                    ma["partes"] == mb["partes"]
                    and ma["comprimentos_cm"] == mb["comprimentos_cm"]
                    and ma["metros"] == mb["metros"]
                )
                detalhes.append(
                    f"- PRETO 150 rodado 2× com {ORCAMENTO_DETERMINISMO:.0f} s de passada "
                    f"({ORCAMENTO_DETERMINISMO / len(partes_a):.0f} s por mesa no K final): "
                    f"comprimentos {ma['comprimentos_cm']} / {mb['comprimentos_cm']} — "
                    f"{'idêntico (determinístico)' if igual else 'DIVERGIU (não convergiu)'}."
                )
            else:
                partes_v2, seg_v2, _, mesas_v2_obj = _rodar_v2(tec, limite, ORCAMENTO_V2)
                m2 = metricas(tec, partes_v2, seg_v2, limite)
                linhas.append(_linha(tec, "v2 (spyrrow+CP-SAT)", limite, partes_v2, seg_v2))
                svg(tec, partes_v2, m2, f"v2 — {nome}", RESULTADOS / f"v2_{tec_id}_{int(limite)}.svg")
                mesas_v2.append(f"- **{nome}** — {_detalhe_mesas(partes_v2, mesas_v2_obj)}")

    cab = "| Tecido | Motor | Limite | Mesas | Metros totais | Aprov. médio | Pior mesa | Tempo | Válido |"
    sep = "|---|---|---:|---:|---:|---:|---:|---:|:-:|"
    titulo = (
        "# v1 × v2 — pedido 000001 / OC-0002\n\n"
        "- v1 = motor atual (nest_worker.js por bounding box + divisão gulosa).\n"
        "- v2 = spyrrow (strip packing, polígono real) + OR-Tools CP-SAT na divisão.\n"
        "- Espaçamento entre peças = 0. Fio vertical → só 0°/180°. Encolhimento 0%.\n"
        "- Os dois v2 de PRETO 150 são duas rodadas iguais, para medir determinismo.\n\n"
    )
    markdown = titulo + "\n".join([cab, sep, *linhas]) + "\n"
    if mesas_v2:
        markdown += "\n## Mesas do v2\n\n" + "\n".join(mesas_v2) + "\n"
    if detalhes:
        markdown += "\n## Determinismo\n\n" + "\n".join(detalhes) + "\n"
    destino = RESULTADOS / "tabela_v1_v2.md"
    destino.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"tabela em {destino}")


if __name__ == "__main__":
    main()
