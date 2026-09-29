"""Candidato A — motor atual, como está hoje (código de produção importado,
sem alteração): nest_worker.js (skyline por bounding box) + divisão gulosa
_partes_do_enfesto. Também roda o "antes" (um risco só, sem limite)."""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from nesting.nesting_bridge import executar  # noqa: E402
from services.nesting_service import _partes_do_enfesto  # noqa: E402

from .comum import LIMITE_CM  # noqa: E402


def _pontos(poligono: list[list[float]], graus: float, x: float, y: float) -> list[list[float]]:
    """Mesma transformação do nest_worker: rotação na origem e canto
    inferior-esquerdo do bounding box em (x, y)."""
    r = graus * math.pi / 180
    c, s = math.cos(r), math.sin(r)
    rot = [[px * c - py * s, px * s + py * c] for px, py in poligono]
    mx, my = min(p[0] for p in rot), min(p[1] for p in rot)
    return [[px - mx + x, py - my + y] for px, py in rot]


def _worker_parts(tec: dict) -> list[dict]:
    return [{k: p[k] for k in ("id", "polygon", "quantity", "rotations")} for p in tec["pecas"]]


def _para_parte(result: dict, por_id: dict) -> list[dict]:
    return [
        {"id": pl["id"], "rotation": pl["rotation"], "points": _pontos(por_id[pl["id"]]["polygon"], pl["rotation"], pl["x"], pl["y"])}
        for pl in result["placements"]
    ]


def rodar(tec: dict, limite: float | None = LIMITE_CM) -> tuple[list[list[dict]], float, dict]:
    parts = _worker_parts(tec)
    por_id = {p["id"]: p for p in parts}
    t0 = time.perf_counter()
    if limite is None:
        partes_res = [(executar(tec["largura_cm"], 1e9, parts), parts)]
    else:
        pares = {p["id"] for p in tec["pecas"] if p["tipo_corte"] in ("par", "par_sem_espelho")}
        partes_res, _ = _partes_do_enfesto(parts, tec["largura_cm"], limite, pares, {})
    seg = time.perf_counter() - t0
    partes = [_para_parte(r, por_id) for r, _ in partes_res]
    # comprimento/aproveitamento reportados pelo próprio motor (para conferir com o banco)
    motor = {"width_used": [r["width_used"] for r, _ in partes_res], "efficiency": [r["efficiency"] for r, _ in partes_res]}
    return partes, seg, motor
