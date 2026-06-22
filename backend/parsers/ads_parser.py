"""Parser para arquivos ADS (formato binário CADZ).

Estrutura do formato CADZ:
  - Cabeçalho ASCII "CADZ vs5.0" (12 bytes)
  - Metadados binários
  - Miniatura JPEG embutida (localizada pelo marcador FF D8, terminada em FF D9)
  - Seções de dados com segmentos de contorno

Cada segmento de contorno reto é codificado como:
  04 00 00 00          (uint32 LE = 4 valores a seguir)
  x0  : float64 LE    (ponto inicial X, em cm)
  y0  : float64 LE    (ponto inicial Y, em cm)
  x1  : float64 LE    (ponto final X, em cm)
  y1  : float64 LE    (ponto final Y, em cm)

Total por segmento: 4 + 4×8 = 36 bytes.

Algoritmo:
  1. Localiza fim do JPEG (FF D9).
  2. Varre o payload restante procurando registros [04 00 00 00 + 4 doubles válidos].
  3. Encadeia segmentos por proximidade de extremidades em polígonos fechados.
  4. Filtra por área (20–30000 cm²) para excluir marcações e molduras.
"""
from __future__ import annotations

import math
import struct
from typing import Any

from shapely.geometry import Polygon

# Limites de área em cm²: exclui marcas/entalhes (< 20) e molduras de plot (> 30000)
_MIN_AREA_CM2 = 20.0
_MAX_AREA_CM2 = 30_000.0

# Tolerância de encadeamento: dois pontos são "o mesmo" se distância < 0.05 cm
_CHAIN_TOL = 0.05

# Coordenadas válidas devem estar neste intervalo (em cm)
_COORD_MIN = -50_000.0
_COORD_MAX = 50_000.0


def parse_ads(caminho: str) -> list[dict[str, Any]]:
    """Lê arquivo ADS (formato CADZ) e extrai contornos das peças.

    Returns:
        Lista de dicts com {nome_sugerido, geometria_json, area_cm2}.
    """
    with open(caminho, "rb") as f:
        data = f.read()

    if not data.startswith(b"CADZ"):
        raise ValueError(
            f"Arquivo ADS inválido: cabeçalho 'CADZ' não encontrado em '{caminho}'."
        )

    # ── 1. Pula a miniatura JPEG embutida ───────────────────────────────────
    jpeg_end = _find_jpeg_end(data)
    payload = data[jpeg_end:] if jpeg_end > 0 else data

    # ── 2. Extrai segmentos de linha ────────────────────────────────────────
    segments = _extract_line_segments(payload)

    print(f"[ADS] {caminho}: payload={len(payload)} bytes, {len(segments)} segs (04h), JPEG offset {jpeg_end}")
    _scan_other_markers(payload)
    if not segments:
        return []

    # ── 3. Encadeia segmentos em polígonos fechados ─────────────────────────
    polygons = _chain_segments_to_polygons(segments)

    print(f"[ADS] {len(polygons)} chains com >=4 pts apos encadeamento")

    # ── 4. Converte para o formato de peças ─────────────────────────────────
    return _polygons_to_pecas(polygons)


# ── Localização do JPEG ──────────────────────────────────────────────────────


def _find_jpeg_end(data: bytes) -> int:
    """Retorna o offset imediatamente após o marcador de fim de JPEG (FF D9)."""
    # Começa na posição 12 para evitar falsos positivos no cabeçalho CADZ
    start = data.find(b"\xff\xd8")
    if start == -1:
        return 0
    for i in range(start, len(data) - 1):
        if data[i] == 0xFF and data[i + 1] == 0xD9:
            return i + 2
    return 0


# ── Diagnóstico de marcadores ────────────────────────────────────────────────


def _scan_other_markers(payload: bytes) -> None:
    """Varre o payload e loga marcadores count≠4 com coordenadas válidas."""
    counts: dict[int, int] = {}
    samples: dict[int, list] = {}
    i = 0
    limit = len(payload) - 4
    while i <= limit:
        count = struct.unpack_from("<I", payload, i)[0]
        if 2 <= count <= 20 and count != 4:
            size_needed = 4 + count * 8
            if i + size_needed <= len(payload):
                vals = struct.unpack_from(f"<{count}d", payload, i + 4)
                if all(math.isfinite(v) and _COORD_MIN < v < _COORD_MAX for v in vals):
                    counts[count] = counts.get(count, 0) + 1
                    if count not in samples:
                        pts = [(round(vals[k * 2], 4), round(vals[k * 2 + 1], 4))
                               for k in range(count // 2)]
                        samples[count] = pts
        i += 1
    if counts:
        print(f"[ADS] outros marcadores no payload: {counts}")
        for c, pts in samples.items():
            print(f"  count={c} exemplo: {pts}")
    else:
        print("[ADS] nenhum outro marcador com coords validas encontrado")


# ── Extração de segmentos ────────────────────────────────────────────────────


def _valid_coord(v: float) -> bool:
    return math.isfinite(v) and _COORD_MIN < v < _COORD_MAX


def _extract_line_segments(
    data: bytes,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Varre o payload procurando registros de segmento de 36 bytes.

    Formato: [04 00 00 00][x0:f64][y0:f64][x1:f64][y1:f64]
    """
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    limit = len(data) - 36
    i = 0

    while i <= limit:
        # Detecta marcador de 4 valores (count = 4)
        if (
            data[i] == 0x04
            and data[i + 1] == 0x00
            and data[i + 2] == 0x00
            and data[i + 3] == 0x00
        ):
            x0, y0, x1, y1 = struct.unpack_from("<4d", data, i + 4)

            if (
                _valid_coord(x0) and _valid_coord(y0)
                and _valid_coord(x1) and _valid_coord(y1)
            ):
                # Descarta segmentos degenerados (ponto inicial = final)
                if math.hypot(x1 - x0, y1 - y0) > 1e-6:
                    segments.append(((x0, y0), (x1, y1)))
                i += 36
                continue

        i += 1

    return segments


# ── Encadeamento em polígonos ────────────────────────────────────────────────


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _chain_segments_to_polygons(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
) -> list[list[tuple[float, float]]]:
    """Encadeia segmentos em polígonos por proximidade de extremidades.

    Estende a cadeia em ambas as direções (frente e trás). Arquivos CADZ às
    vezes omitem o lado reto alinhado ao fio/dobra, por isso também fecha
    cadeias abertas com >= 3 segmentos (>= 4 pontos) via segmento implícito.
    """
    used = [False] * len(segments)
    polygons: list[list[tuple[float, float]]] = []

    for start_idx, (a0, b0) in enumerate(segments):
        if used[start_idx]:
            continue

        chain: list[tuple[float, float]] = [a0, b0]
        used[start_idx] = True

        # Expande pelo final da cadeia
        while True:
            tail = chain[-1]
            found = False
            for j, (a, b) in enumerate(segments):
                if used[j]:
                    continue
                if _dist(a, tail) < _CHAIN_TOL:
                    chain.append(b)
                    used[j] = True
                    found = True
                    break
                elif _dist(b, tail) < _CHAIN_TOL:
                    chain.append(a)
                    used[j] = True
                    found = True
                    break
            if not found:
                break

        # Expande pelo início da cadeia (sentido reverso)
        while True:
            head = chain[0]
            found = False
            for j, (a, b) in enumerate(segments):
                if used[j]:
                    continue
                if _dist(b, head) < _CHAIN_TOL:
                    chain.insert(0, a)
                    used[j] = True
                    found = True
                    break
                elif _dist(a, head) < _CHAIN_TOL:
                    chain.insert(0, b)
                    used[j] = True
                    found = True
                    break
            if not found:
                break

        fechado = _dist(chain[0], chain[-1]) < _CHAIN_TOL
        print(
            f"[ADS] chain start_idx={start_idx}: {len(chain)} pts, "
            f"gap={_dist(chain[0], chain[-1]):.4f} cm "
            f"-> {'fechado' if fechado else 'aberto'}"
            f"{'' if len(chain) >= 4 else ' [IGNORADO <4 pts]'}"
        )

        if len(chain) < 4:
            continue

        # Polígono fechado (caso ideal)
        if fechado:
            polygons.append(chain)
        else:
            # Cadeia aberta: fecha com segmento implícito (lado reto/dobra omitido no arquivo)
            polygons.append(chain + [chain[0]])

    return polygons


# ── Conversão para peças ─────────────────────────────────────────────────────


def _polygons_to_pecas(
    polygons: list[list[tuple[float, float]]],
) -> list[dict[str, Any]]:
    """Filtra polígonos por área e retorna no formato geometria_json (GeoJSON Polygon)."""
    pecas: list[dict[str, Any]] = []
    idx = 1

    for pts in polygons:
        try:
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            area = float(poly.area)
        except Exception as exc:
            print(f"[ADS] poly invalido ({len(pts)} pts): {exc}")
            continue

        aceito = _MIN_AREA_CM2 <= area <= _MAX_AREA_CM2
        print(
            f"[ADS] poly {idx}: {len(pts)} pts, area={area:.2f} cm2 "
            f"-> {'ACEITO' if aceito else 'REJEITADO'}"
            f"{'' if aceito else f' (fora de [{_MIN_AREA_CM2}, {_MAX_AREA_CM2}])'}"
        )
        if not aceito:
            continue

        coords_list = [list(p) for p in poly.exterior.coords]
        pecas.append(
            {
                "nome_sugerido": f"Peça {idx}",
                "geometria_json": {
                    "type": "Polygon",
                    "coordinates": [coords_list],
                },
                "area_cm2": round(area, 4),
            }
        )
        idx += 1

    return pecas
