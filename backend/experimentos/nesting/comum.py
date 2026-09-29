"""Utilidades comuns do benchmark: carga das peças, validação, métricas e SVG.

Referencial (o mesmo do motor atual): x = largura do tecido (0..W),
y = comprimento (o eixo minimizado). Cada "parte" é uma lista de peças
posicionadas: {"id", "rotation", "points": [[x, y], ...]}.
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path

from shapely.geometry import Polygon
from shapely.strtree import STRtree

AQUI = Path(__file__).parent
DADOS = AQUI / "dados" / "pedido000001_oc0002.json"
RESULTADOS = AQUI / "resultados"
LIMITE_CM = 150.0
EPS = 1e-3


def carregar() -> dict:
    return json.loads(DADOS.read_text(encoding="utf-8"))


def area(pts: list[list[float]]) -> float:
    n = len(pts)
    return abs(sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))) / 2


def normalizar_parte(parte: list[dict]) -> list[dict]:
    """Desloca a parte para começar em y=0 (cada parte é uma mesa/risco)."""
    if not parte:
        return parte
    y0 = min(p[1] for pc in parte for p in pc["points"])
    return [{**pc, "points": [[x, y - y0] for x, y in pc["points"]]} for pc in parte]


def comprimento(parte: list[dict]) -> float:
    if not parte:
        return 0.0
    ys = [p[1] for pc in parte for p in pc["points"]]
    return max(ys) - min(ys)


def validar(tec: dict, partes: list[list[dict]], limite: float | None) -> dict:
    """Checa sobreposição, largura, contagem e limite. Retorna os problemas."""
    W = tec["largura_cm"]
    problemas: list[str] = []
    pedido = {p["id"]: p["quantity"] for p in tec["pecas"]}
    contagem: dict[str, int] = {}
    pares_divididos = 0
    pares = {p["id"] for p in tec["pecas"] if p["tipo_corte"] in ("par", "par_sem_espelho")}
    for i, parte in enumerate(partes, start=1):
        polys = [Polygon(pc["points"]).buffer(0) for pc in parte]
        for pc, pg in zip(parte, polys):
            contagem[pc["id"]] = contagem.get(pc["id"], 0) + 1
            minx, _, maxx, _ = pg.bounds
            if minx < -0.05 or maxx > W + 0.05:
                problemas.append(f"parte {i}: peça fora da largura ({minx:.2f}..{maxx:.2f})")
        tree = STRtree(polys)
        sobreposicao = 0.0
        for a, pa in enumerate(polys):
            for b in tree.query(pa):
                if b > a:
                    sobreposicao += pa.intersection(polys[b]).area
        if sobreposicao > 1.0:  # cm² — tolerância numérica de peças encostadas
            problemas.append(f"parte {i}: sobreposição de {sobreposicao:.1f} cm²")
        if limite and comprimento(parte) > limite + 0.05:
            problemas.append(f"parte {i}: {comprimento(parte):.1f} cm > limite {limite:g}")
        por_id: dict[str, int] = {}
        for pc in parte:
            por_id[pc["id"]] = por_id.get(pc["id"], 0) + 1
        pares_divididos += sum(1 for pid, n in por_id.items() if pid in pares and n % 2)
    for pid, q in pedido.items():
        if contagem.get(pid, 0) != q:
            problemas.append(f"peça {pid[:6]}: {contagem.get(pid, 0)} de {q}")
    return {"problemas": problemas, "pares_divididos": pares_divididos // 2 if pares_divididos else 0}


def metricas(tec: dict, partes: list[list[dict]], segundos: float, limite: float | None = LIMITE_CM) -> dict:
    W = tec["largura_cm"]
    comps = [comprimento(p) for p in partes]
    efs = [sum(area(pc["points"]) for pc in p) / (W * c) if c else 0 for p, c in zip(partes, comps)]
    area_total = sum(area(pc["points"]) for p in partes for pc in p)
    total = sum(comps)
    v = validar(tec, partes, limite)
    return {
        "metros": round(total / 100, 3),
        "partes": len(partes),
        "comprimentos_cm": [round(c, 1) for c in comps],
        "aproveitamento_medio": round(area_total / (W * total), 4) if total else 0,
        "aproveitamento_pior": round(min(efs), 4) if efs else 0,
        "aproveitamento_partes": [round(e, 4) for e in efs],
        "segundos": round(segundos, 2),
        "valido": not v["problemas"],
        "problemas": v["problemas"],
        "pares_divididos": v["pares_divididos"],
    }


def limite_inferior(tec: dict) -> dict:
    """Comprimento com 100% de aproveitamento e nº mínimo de mesas."""
    area_total = sum(area(p["polygon"]) * p["quantity"] for p in tec["pecas"])
    comp = area_total / tec["largura_cm"]
    return {"area_cm2": round(area_total), "metros_100pct": round(comp / 100, 3), "partes_min": math.ceil(comp / LIMITE_CM)}


# ── SVG ──────────────────────────────────────────────────────────────────────

_CORES = {
    "FRENTE": "#4e79a7",
    "COSTAS": "#f28e2b",
    "CÓS COSTAS": "#59a14f",
    "CÓS FRENTE": "#e15759",
}


def svg(tec: dict, partes: list[list[dict]], m: dict, titulo: str, destino: Path) -> None:
    """Desenha as partes lado a lado; comprimento na horizontal."""
    W = tec["largura_cm"]
    nomes = {p["id"]: p for p in tec["pecas"]}
    gap = 20
    comps = [max(comprimento(p), 1) for p in partes]
    total_w = sum(comps) + gap * (len(partes) + 1)
    esc = 4  # px por cm
    alt = W + 70
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w * esc:.0f}" height="{alt * esc:.0f}" '
        f'viewBox="0 0 {total_w:.1f} {alt:.1f}" font-family="sans-serif">',
        f'<rect width="100%" height="100%" fill="#fff"/>',
        f'<text x="{gap}" y="12" font-size="7" font-weight="bold">{html.escape(titulo)}</text>',
        f'<text x="{gap}" y="22" font-size="5">{m["metros"]:.2f} m · {m["partes"]} parte(s) · '
        f'aprov. médio {m["aproveitamento_medio"] * 100:.1f}% · pior {m["aproveitamento_pior"] * 100:.1f}% · '
        f'{m["segundos"]:.1f}s{" · INVÁLIDO" if not m["valido"] else ""}</text>',
    ]
    x0 = gap
    for i, (parte, c) in enumerate(zip(partes, comps)):
        oy = 35
        ef = m["aproveitamento_partes"][i] * 100
        out.append(f'<text x="{x0}" y="{oy - 3}" font-size="4.5">Parte {i + 1}: {c:.1f} cm · {ef:.1f}%</text>')
        out.append(f'<rect x="{x0}" y="{oy}" width="{c:.2f}" height="{W}" fill="#f4f4f4" stroke="#999" stroke-width="0.4"/>')
        out.append(
            f'<rect x="{x0}" y="{oy}" width="{LIMITE_CM}" height="{W}" fill="none" stroke="#c00" '
            f'stroke-width="0.3" stroke-dasharray="2 2"/>'
        )
        y0 = min((p[1] for pc in parte for p in pc["points"]), default=0)
        for pc in parte:
            info = nomes.get(pc["id"], {})
            cor = _CORES.get((info.get("peca") or "").upper(), "#bab0ac")
            pts = " ".join(f"{x0 + (y - y0):.2f},{oy + x:.2f}" for x, y in pc["points"])
            out.append(f'<polygon points="{pts}" fill="{cor}" fill-opacity="0.75" stroke="#222" stroke-width="0.25"/>')
            cx = sum(p[1] - y0 for p in pc["points"]) / len(pc["points"]) + x0
            cy = sum(p[0] for p in pc["points"]) / len(pc["points"]) + oy
            out.append(
                f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="3.2" text-anchor="middle">'
                f'{html.escape(info.get("nome", "?"))}{" ↻" if pc.get("rotation") else ""}</text>'
            )
        x0 += c + gap
    out.append("</svg>")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(out), encoding="utf-8")
