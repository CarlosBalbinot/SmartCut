"""nesting_bridge.py — Ponte Python → Node.js para o motor de nesting.

Serializa o job em JSON, passa via stdin ao nest_worker.js e desserializa
o resultado. Todas as coordenadas são em centímetros.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

from config import settings

if getattr(sys, 'frozen', False):
    _WORKER = Path(sys._MEIPASS) / "nesting" / "nest_worker.js"
else:
    _WORKER = Path(__file__).parent / "nest_worker.js"


def build_polygon(geometria_json: dict | None, area_cm2: float | None) -> list[list[float]]:
    """Extrai o polígono exterior do geometria_json (formato GeoJSON Polygon).

    Retorna uma lista de pontos [[x, y], ...] em cm.
    Se não houver geometria, cria um quadrado aproximado a partir da área.
    """
    if geometria_json:
        geo = geometria_json
        # Formato GeoJSON: {"type": "Polygon", "coordinates": [[[x,y],...], ...]}
        if isinstance(geo, dict) and geo.get("type") == "Polygon":
            ring = geo["coordinates"][0]
            return [[float(p[0]), float(p[1])] for p in ring]
        # Formato legado: lista direta de pontos
        if isinstance(geo, list) and geo:
            return [[float(p[0]), float(p[1])] for p in geo]

    # Fallback: retângulo aproximado pela área
    side = math.sqrt(float(area_cm2)) if area_cm2 and float(area_cm2) > 0 else 10.0
    w, h = side, side
    return [[0.0, 0.0], [w, 0.0], [w, h], [0.0, h], [0.0, 0.0]]


def executar(
    bin_width_cm: float,
    bin_height_cm: float,
    parts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Executa o nest_worker.js e retorna placements + métricas.

    Args:
        bin_width_cm:  Largura útil do tecido em cm (dimensão fixa).
        bin_height_cm: Comprimento máximo permitido em cm (orçamento).
        parts: Lista de dicts com as chaves:
            - id (str)
            - polygon ([[x, y], ...])  — pode ser obtido via _build_polygon
            - quantity (int)
            - rotations ([0, 90, 180, 270] ou subconjunto)

    Returns:
        {
          "placements": [{"id", "x", "y", "rotation"}, ...],
          "efficiency": float,   # 0–1
          "width_used": float,   # comprimento consumido em cm
        }

    Raises:
        RuntimeError: se o node não estiver disponível ou o worker falhar.
    """
    payload = {
        "bin": {"width": bin_width_cm, "height": bin_height_cm},
        "parts": parts,
    }

    try:
        proc = subprocess.run(
            ["node", str(_WORKER)],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=settings.nesting_timeout_sec,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Node.js não encontrado. Instale o Node.js para usar o motor de nesting."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Motor de nesting excedeu o limite de tempo "
            f"({settings.nesting_timeout_sec}s). Reduza o número de peças."
        )

    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        raise RuntimeError(f"nest_worker falhou:\n{stderr}")

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Resposta inválida do nest_worker: {exc}") from exc
