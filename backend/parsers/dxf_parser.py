"""Parser para arquivos DXF.

Extrai peças a partir de LWPOLYLINE, POLYLINE, SPLINE e LINE fechadas.
Linhas independentes são agrupadas por layer quando formam contornos.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import ezdxf
from ezdxf.math import Vec2
from shapely.geometry import Polygon
from shapely.ops import unary_union


MIN_AREA_CM2 = 1.0  # ignora entidades minúsculas (pontos de marcação)


def parse_dxf(caminho: str) -> list[dict[str, Any]]:
    """Lê arquivo DXF e extrai polígonos de peças.

    Entidades suportadas: LWPOLYLINE, POLYLINE, SPLINE, LINE.
    LINE são agrupadas por layer e unidas em polígonos quando fecham.

    Returns:
        Lista de dicts com {nome_sugerido, geometria_json, area_cm2}.
    """
    doc = ezdxf.readfile(caminho)
    msp = doc.modelspace()

    pecas: list[dict[str, Any]] = []
    idx = 1

    # Coletor de segmentos LINE por layer (para montagem de contornos)
    lines_by_layer: dict[str, list[tuple[Vec2, Vec2]]] = defaultdict(list)

    for ent in msp:
        tipo = ent.dxftype()
        pontos: list[tuple[float, float]] | None = None

        if tipo == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in ent.get_points()]
            if len(pts) >= 3:
                pontos = pts

        elif tipo == "POLYLINE":
            try:
                pts = [(v.dxf.location.x, v.dxf.location.y) for v in ent.vertices]
                if len(pts) >= 3:
                    pontos = pts
            except Exception:
                pass

        elif tipo == "SPLINE":
            try:
                pts = [(p[0], p[1]) for p in ent.control_points]
                if len(pts) >= 3:
                    pontos = pts
            except Exception:
                pass

        elif tipo == "LINE":
            layer = ent.dxf.layer
            try:
                start = Vec2(ent.dxf.start.x, ent.dxf.start.y)
                end = Vec2(ent.dxf.end.x, ent.dxf.end.y)
                lines_by_layer[layer].append((start, end))
            except Exception:
                pass

        if pontos is not None:
            result = _make_peca(pontos, idx)
            if result:
                pecas.append(result)
                idx += 1

    # Tenta montar polígonos a partir dos segmentos LINE por layer
    for layer, segments in lines_by_layer.items():
        polys = _segments_to_polygons(segments)
        for poly in polys:
            result = _poly_to_peca(poly, idx)
            if result:
                pecas.append(result)
                idx += 1

    return pecas


def _make_peca(pontos: list[tuple[float, float]], idx: int) -> dict[str, Any] | None:
    try:
        poly = Polygon(pontos)
        if not poly.is_valid:
            poly = poly.buffer(0)
        return _poly_to_peca(poly, idx)
    except Exception:
        return None


def _poly_to_peca(poly: Polygon, idx: int) -> dict[str, Any] | None:
    try:
        area = float(poly.area)
        if area < MIN_AREA_CM2:
            return None
        coords = [list(p) for p in poly.exterior.coords]
        return {
            "nome_sugerido": f"Peça {idx}",
            "geometria_json": {"type": "Polygon", "coordinates": [coords]},
            "area_cm2": round(area, 4),
        }
    except Exception:
        return None


def _segments_to_polygons(segments: list[tuple[Vec2, Vec2]]) -> list[Polygon]:
    """Tenta encadear segmentos LINE em polígonos fechados (simplificado)."""
    if not segments:
        return []

    # Monta grafo de adjacência por endpoints (tolerância de 1e-6)
    TOL = 1e-6
    used = [False] * len(segments)
    polygons: list[Polygon] = []

    for start_idx in range(len(segments)):
        if used[start_idx]:
            continue
        chain: list[Vec2] = [segments[start_idx][0], segments[start_idx][1]]
        used[start_idx] = True

        while True:
            tail = chain[-1]
            found = False
            for j, (a, b) in enumerate(segments):
                if used[j]:
                    continue
                if (a - tail).magnitude < TOL:
                    chain.append(b)
                    used[j] = True
                    found = True
                    break
                elif (b - tail).magnitude < TOL:
                    chain.append(a)
                    used[j] = True
                    found = True
                    break
            if not found:
                break

        # Verifica se a cadeia fecha
        if len(chain) >= 3 and (chain[0] - chain[-1]).magnitude < TOL:
            try:
                pts = [(v.x, v.y) for v in chain]
                poly = Polygon(pts)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if poly.area >= MIN_AREA_CM2:
                    polygons.append(poly)
            except Exception:
                pass

    return polygons
