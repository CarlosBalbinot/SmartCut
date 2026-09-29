"""Chamadas aos motores externos do benchmark (processos separados).

  svgnest(...)  — svgnest_headless.js (Node) — várias mesas (bin packing) ou faixa
  sparrow(...)  — sparrow.exe (Rust, jagua-rs) — só faixa (strip packing)
  lbf(...)      — lbf.exe (referência do jagua-rs) — faixa ou várias mesas

Todos recebem as peças no referencial do SmartCut (x = largura, y =
comprimento) e devolvem partes no formato do comum.py. Sparrow/lbf
trabalham com a faixa no eixo x (altura fixa = largura do tecido), então
trocamos x↔y na ida e na volta (reflexão; 0°/180° não mudam).
"""

from __future__ import annotations

import json
import math
import subprocess
import tempfile
import time
from pathlib import Path

AQUI = Path(__file__).parent
TOOLS = AQUI / ".tools"
SPARROW = TOOLS / "sparrow" / "target" / "release" / "sparrow.exe"
LBF = TOOLS / "jagua-rs" / "target" / "release" / "lbf.exe"


def _instancias(pecas: list[dict]) -> list[dict]:
    return [{k: p[k] for k in ("id", "polygon", "quantity", "rotations")} for p in pecas if p["quantity"] > 0]


# ── SVGnest ──────────────────────────────────────────────────────────────────


def svgnest(pecas: list[dict], largura: float, comprimento: float, **config) -> tuple[list[list[dict]], dict]:
    """Uma mesa de `comprimento` × `largura`; o SVGnest abre mesas novas
    enquanto sobrar peça (fitness = nº de mesas + compactação)."""
    job = {"bin": {"length": comprimento, "width": largura}, "parts": _instancias(pecas), "config": config}
    proc = subprocess.run(
        ["node", str(AQUI / "svgnest_headless.js")],
        input=json.dumps(job),
        capture_output=True,
        text=True,
        timeout=3600,
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    res = json.loads(proc.stdout)
    partes = [[{"id": pc["id"], "rotation": pc["rotation"], "points": pc["points"]} for pc in b] for b in res["bins"]]
    return partes, {k: res[k] for k in ("fitness", "generations", "evaluations", "seconds", "unplaced")}


# ── jagua-rs (sparrow / lbf) ─────────────────────────────────────────────────


def _item(i: int, p: dict) -> dict:
    pts = [[y, x] for x, y in p["polygon"]]
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    return {
        "id": i,
        "demand": p["quantity"],
        "allowed_orientations": [float(r) for r in p["rotations"]],
        "shape": {"type": "simple_polygon", "data": pts},
    }


def _transformar(pts: list[list[float]], rot: float, tx: float, ty: float) -> list[list[float]]:
    r = math.radians(rot)
    c, s = math.cos(r), math.sin(r)
    return [[x * c - y * s + tx, x * s + y * c + ty] for x, y in pts]


def _layout(layout: dict, shapes: dict[int, list], ids: dict[int, str]) -> list[dict]:
    parte = []
    for pl in layout["placed_items"]:
        t = pl["transformation"]
        pts = _transformar(shapes[pl["item_id"]], t["rotation"], *t["translation"])
        parte.append({"id": ids[pl["item_id"]], "rotation": t["rotation"] % 360, "points": [[y, x] for x, y in pts]})
    return parte


def sparrow(pecas: list[dict], largura: float, segundos: float, seed: int = 1) -> tuple[list[dict], dict]:
    """Faixa única (sem limite de comprimento). Retorna (parte, info)."""
    pecas = [p for p in pecas if p["quantity"] > 0]
    ids = {i: p["id"] for i, p in enumerate(pecas)}
    inst = {"name": "job", "items": [_item(i, p) for i, p in enumerate(pecas)], "strip_height": largura}
    with tempfile.TemporaryDirectory(dir=TOOLS) as tmp:
        Path(tmp, "job.json").write_text(json.dumps(inst))
        t0 = time.perf_counter()
        proc = subprocess.run(
            [str(SPARROW), "-i", "job.json", "-t", str(int(max(segundos, 1))), "-s", str(seed)],
            cwd=tmp,
            capture_output=True,
            text=True,
        )
        seg = time.perf_counter() - t0
        if proc.returncode:
            raise RuntimeError(proc.stderr[-2000:] or proc.stdout[-2000:])
        out = json.loads(Path(tmp, "output", "final_job.json").read_text())
    shapes = {it["id"]: it["shape"]["data"] for it in out["items"]}
    sol = out["solution"]
    return _layout(sol["layout"], shapes, ids), {"segundos": seg, "density": sol["density"], "strip_cm": sol["strip_width"]}


def lbf_bpp(pecas: list[dict], largura: float, comprimento: float, n_samples: int = 5000, seed: int = 1) -> tuple[list[list[dict]], dict]:
    """Várias mesas comprimento × largura (bin packing, left-bottom-fill)."""
    pecas = [p for p in pecas if p["quantity"] > 0]
    ids = {i: p["id"] for i, p in enumerate(pecas)}
    n = sum(p["quantity"] for p in pecas)
    rect = [[0, 0], [comprimento, 0], [comprimento, largura], [0, largura]]
    inst = {
        "name": "job",
        "items": [_item(i, p) for i, p in enumerate(pecas)],
        "bins": [{"id": 0, "cost": 1, "stock": n, "shape": {"type": "simple_polygon", "data": rect}}],
    }
    cfg = json.loads((TOOLS / "jagua-rs" / "assets" / "config_lbf.json").read_text())
    cfg.update({"prng_seed": seed, "n_samples": n_samples})
    with tempfile.TemporaryDirectory(dir=TOOLS) as tmp:
        Path(tmp, "job.json").write_text(json.dumps(inst))
        Path(tmp, "cfg.json").write_text(json.dumps(cfg))
        t0 = time.perf_counter()
        proc = subprocess.run(
            [str(LBF), "-i", "job.json", "-s", "sol", "-c", "cfg.json", "-p", "bpp", "-l", "warn"],
            cwd=tmp,
            capture_output=True,
            text=True,
        )
        seg = time.perf_counter() - t0
        if proc.returncode:
            raise RuntimeError(proc.stderr[-2000:] or proc.stdout[-2000:])
        sol_json = next(Path(tmp, "sol").glob("*.json"))
        out = json.loads(sol_json.read_text())
    shapes = {it["id"]: it["shape"]["data"] for it in out["items"]}
    sol = out["solution"]
    layouts = sol.get("layouts") or [sol["layout"]]
    return [_layout(l, shapes, ids) for l in layouts], {"segundos": seg}
