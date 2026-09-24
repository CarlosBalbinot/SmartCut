"""Parser para arquivos DXF.

Extrai peças a partir de LWPOLYLINE, POLYLINE, SPLINE e LINE fechadas.
Linhas independentes são agrupadas por layer quando formam contornos.

Também varre textos (TEXT/MTEXT) para sugerir nomes de peça e linhas
soltas para detectar o sentido do fio.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any

import ezdxf
from ezdxf.math import Vec2
from shapely.geometry import Polygon


MIN_AREA_CM2 = 1.0  # ignora entidades minúsculas (pontos de marcação)
DISTANCIA_MAX_TEXTO_CM = 50.0  # limite para associar texto a uma peça
FATOR_LINHA_FIO = 2.0  # linha do fio deve ser > 2x a mediana das demais


def parse_dxf(caminho: str) -> list[dict[str, Any]]:
    """Lê arquivo DXF e extrai polígonos de peças.

    Entidades suportadas: LWPOLYLINE, POLYLINE, SPLINE, LINE.
    LINE são agrupadas por layer e unidas em polígonos quando fecham.

    Returns:
        Lista de dicts com {nome_sugerido, geometria_json, area_cm2,
        sentido_fio_detectado}.
    """
    doc = ezdxf.readfile(caminho)
    msp = doc.modelspace()

    pecas: list[dict[str, Any]] = []
    poligonos: list[Polygon] = []
    idx = 1

    # Coletor de segmentos LINE por layer (para montagem de contornos)
    lines_by_layer: dict[str, list[tuple[Vec2, Vec2]]] = defaultdict(list)
    # Todas as linhas soltas do desenho (para detecção de sentido do fio)
    todas_linhas: list[tuple[Vec2, Vec2]] = []

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
                todas_linhas.append((start, end))
            except Exception:
                pass

        if pontos is not None:
            resultado = _make_peca(pontos, idx)
            if resultado:
                dict_peca, poly = resultado
                pecas.append(dict_peca)
                poligonos.append(poly)
                idx += 1

    # Tenta montar polígonos a partir dos segmentos LINE por layer
    for _layer, segments in lines_by_layer.items():
        for poly in _segments_to_polygons(segments):
            resultado = _poly_to_peca(poly, idx)
            if resultado:
                dict_peca, poly_valido = resultado
                pecas.append(dict_peca)
                poligonos.append(poly_valido)
                idx += 1

    textos = _extrair_textos(msp)
    for dict_peca, poly in zip(pecas, poligonos):
        centroide = poly.centroid
        nome = _texto_mais_proximo(centroide, textos)
        if nome:
            dict_peca["nome_sugerido"] = nome
        dict_peca["sentido_fio_detectado"] = _detectar_sentido_fio(poly, todas_linhas)

    return pecas


def _make_peca(pontos: list[tuple[float, float]], idx: int) -> tuple[dict[str, Any], Polygon] | None:
    try:
        poly = Polygon(pontos)
        if not poly.is_valid:
            poly = poly.buffer(0)
        return _poly_to_peca(poly, idx)
    except Exception:
        return None


def _poly_to_peca(poly: Polygon, idx: int) -> tuple[dict[str, Any], Polygon] | None:
    try:
        area = float(poly.area)
        if area < MIN_AREA_CM2:
            return None
        coords = [list(p) for p in poly.exterior.coords]
        dict_peca = {
            "nome_sugerido": f"Peça {idx}",
            "geometria_json": {"type": "Polygon", "coordinates": [coords]},
            "area_cm2": round(area, 4),
            "sentido_fio_detectado": None,
        }
        return dict_peca, poly
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


# ── Nomes de peça a partir de textos (TEXT/MTEXT) ──────────────────────


def _extrair_textos(msp) -> list[tuple[Vec2, str]]:
    """Varre TEXT/MTEXT do modelspace e retorna (posição, texto) já filtrados."""
    textos: list[tuple[Vec2, str]] = []
    for ent in msp:
        tipo = ent.dxftype()
        conteudo = None
        posicao = None

        if tipo == "TEXT":
            try:
                conteudo = ent.dxf.text
                posicao = Vec2(ent.dxf.insert.x, ent.dxf.insert.y)
            except Exception:
                continue

        elif tipo == "MTEXT":
            try:
                conteudo = ent.plain_text() if hasattr(ent, "plain_text") else ent.text
                posicao = Vec2(ent.dxf.insert.x, ent.dxf.insert.y)
            except Exception:
                continue

        if conteudo is None or posicao is None:
            continue

        conteudo = conteudo.strip()
        if not conteudo or _is_texto_quantidade(conteudo):
            continue

        textos.append((posicao, conteudo))

    return textos


def _is_texto_quantidade(texto: str) -> bool:
    """Filtra textos que indicam quantidade ('1 peça', '2 pares', '34')."""
    t = texto.strip()
    if not t:
        return True
    somente_numero = t.replace(",", "").replace(".", "")
    if somente_numero.isdigit():
        return True
    return t[0].isdigit()


def _texto_mais_proximo(centroide, textos: list[tuple[Vec2, str]]) -> str | None:
    melhor_texto: str | None = None
    melhor_dist = DISTANCIA_MAX_TEXTO_CM
    for posicao, texto in textos:
        dist = math.hypot(posicao.x - centroide.x, posicao.y - centroide.y)
        if dist <= melhor_dist:
            melhor_dist = dist
            melhor_texto = texto
    return melhor_texto


# ── Detecção do sentido do fio ──────────────────────────────────────────


def _detectar_sentido_fio(poly: Polygon, linhas: list[tuple[Vec2, Vec2]]) -> str | None:
    minx, miny, maxx, maxy = poly.bounds
    candidatas: list[tuple[float, Vec2, Vec2]] = []
    for a, b in linhas:
        if minx <= a.x <= maxx and miny <= a.y <= maxy and minx <= b.x <= maxx and miny <= b.y <= maxy:
            candidatas.append(((a - b).magnitude, a, b))

    if len(candidatas) < 2:
        return None

    candidatas.sort(key=lambda c: c[0], reverse=True)
    comprimento_maior, a, b = candidatas[0]
    mediana_outras = statistics.median(c[0] for c in candidatas[1:])

    if mediana_outras <= 0 or comprimento_maior <= FATOR_LINHA_FIO * mediana_outras:
        return None

    angulo = math.degrees(math.atan2(b.y - a.y, b.x - a.x)) % 360
    return _classificar_sentido(angulo)


def _classificar_sentido(angulo: float) -> str | None:
    if 80 <= angulo <= 100 or 260 <= angulo <= 280:
        return "vertical"
    if 0 <= angulo <= 10 or 170 <= angulo <= 190:
        return "horizontal"
    if 40 <= angulo <= 50 or 220 <= angulo <= 230:
        return "45graus"
    return None
