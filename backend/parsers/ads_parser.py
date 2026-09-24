"""Parser para arquivos ADS (formato binário CADZ).

Estrutura do formato CADZ:
  - Cabeçalho ASCII "CADZ vs5.0" (12 bytes)
  - Metadados binários
  - Miniatura JPEG embutida (localizada pelo marcador FF D8, terminada em FF D9)
  - Seções de dados com registros [uint32 count LE][count × float64 LE]

Registros reconhecidos após o JPEG:
  count=4 (36 bytes): segmento de contorno reto [x0,y0,x1,y1], em cm.
      Vários segmentos consecutivos formam o contorno de UMA peça.
  count=2 (20 bytes): marcador de fronteira entre peças — fecha o grupo
      de segmentos acumulado até aqui e inicia um novo (peça seguinte).
  count=5 / count=8: metadados (não são geometria de peça) — ignorados.

Algoritmo:
  1. Localiza fim do JPEG (FF D9).
  2. Varre o payload restante agrupando os segmentos count=4 em grupos,
     fechando o grupo atual sempre que encontra um marcador count=2
     (_extract_grouped_segments). Isso evita que segmentos de peças
     diferentes sejam encadeados entre si.
  3. Encadeia os segmentos de CADA grupo separadamente em polígonos
     fechados (_chain_segments_to_polygons chamado por grupo).
  4. Filtra por área (20–30000 cm²) para excluir marcações e molduras,
     mantendo todos os polígonos aceitos de cada grupo — não só o maior
     (permite peças com furo interno, por exemplo).
"""

from __future__ import annotations

import math
import struct
from typing import Any

from shapely.geometry import Polygon

# Limites de área em cm²: exclui marcas/entalhes (< 20) e molduras de plot (> 30000)
_MIN_AREA_CM2 = 20.0
_MAX_AREA_CM2 = 30_000.0

# Coordenadas válidas devem estar neste intervalo (em cm)
_COORD_MIN = -50_000.0
_COORD_MAX = 50_000.0

# Tolerância de encadeamento padrão (cm): dois pontos são "o mesmo" se
# distância < 0.05 cm. Exposta como parâmetro em vez de constante fixa,
# para permitir ajuste por chamador sem editar este módulo.
_DEFAULT_CHAIN_TOL = 0.05


def parse_ads(caminho: str, chain_tol: float = _DEFAULT_CHAIN_TOL) -> list[dict[str, Any]]:
    """Lê arquivo ADS (formato CADZ) e extrai contornos das peças.

    Args:
        caminho: caminho do arquivo .ads.
        chain_tol: tolerância (cm) de encadeamento de extremidades.

    Returns:
        Lista de dicts com {nome_sugerido, geometria_json, area_cm2}.
    """
    with open(caminho, "rb") as f:
        data = f.read()

    if not data.startswith(b"CADZ"):
        raise ValueError(f"Arquivo ADS inválido: cabeçalho 'CADZ' não encontrado em '{caminho}'.")

    # ── 1. Pula a miniatura JPEG embutida ───────────────────────────────────
    jpeg_end = _find_jpeg_end(data)
    payload = data[jpeg_end:] if jpeg_end > 0 else data

    # ── 2. Extrai segmentos de linha agrupados por peça (separador count=2) ─
    grupos = _extract_grouped_segments(payload)
    total_segs = sum(len(g) for g in grupos)

    print(
        f"[ADS] {caminho}: payload={len(payload)} bytes, {total_segs} segs (04h) "
        f"em {len(grupos)} grupos, JPEG offset {jpeg_end}"
    )
    _scan_other_markers(payload)
    print(f"[ADS] {len(grupos)} grupos encontrados (separados por count=2)")

    if not grupos:
        return []

    # ── 3. Encadeia cada grupo independentemente e filtra por área ──────────
    pecas: list[dict[str, Any]] = []
    idx = 1
    for gi, segmentos_grupo in enumerate(grupos, start=1):
        polygons = _chain_segments_to_polygons(segmentos_grupo, tol=chain_tol, group_label=gi)
        pecas_grupo, idx = _polygons_to_pecas(polygons, start_idx=idx)
        print(f"[ADS] grupo {gi}: {len(segmentos_grupo)} segmentos -> {len(pecas_grupo)} poligonos aceitos")
        pecas.extend(pecas_grupo)

    print(f"[ADS] total: {len(pecas)} poligonos extraidos")
    return pecas


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
                        pts = [(round(vals[k * 2], 4), round(vals[k * 2 + 1], 4)) for k in range(count // 2)]
                        samples[count] = pts
        i += 1
    if counts:
        print(f"[ADS] outros marcadores no payload: {counts}")
        for c, pts in samples.items():
            print(f"  count={c} exemplo: {pts}")
    else:
        print("[ADS] nenhum outro marcador com coords validas encontrado")


# ── Extração de segmentos agrupados por peça ─────────────────────────────────


def _valid_coord(v: float) -> bool:
    return math.isfinite(v) and _COORD_MIN < v < _COORD_MAX


def _extract_grouped_segments(
    data: bytes,
) -> list[list[tuple[tuple[float, float], tuple[float, float]]]]:
    """Varre o payload agrupando segmentos count=4 em peças.

    Formatos reconhecidos (uint32 LE + N × float64 LE):
      count=4 (36 bytes): segmento de contorno [x0,y0,x1,y1] -> soma ao
          grupo (peça) atual.
      count=2 (20 bytes): marcador de fronteira -> fecha o grupo atual
          (se tiver segmentos) e inicia um novo.
      count=5 (44 bytes) / count=8 (68 bytes): metadados, ignorados
          (apenas pulados).

    Qualquer outro byte que não abra um registro reconhecido avança 1 byte
    por vez, pois o payload não é estritamente alinhado a registros fixos.
    """
    groups: list[list[tuple[tuple[float, float], tuple[float, float]]]] = []
    current: list[tuple[tuple[float, float], tuple[float, float]]] = []

    n = len(data)
    i = 0
    while i <= n - 4:
        count = struct.unpack_from("<I", data, i)[0]

        if count == 4:
            end = i + 4 + 4 * 8
            if end <= n:
                x0, y0, x1, y1 = struct.unpack_from("<4d", data, i + 4)
                if (
                    _valid_coord(x0)
                    and _valid_coord(y0)
                    and _valid_coord(x1)
                    and _valid_coord(y1)
                    and math.hypot(x1 - x0, y1 - y0) > 1e-6
                ):
                    current.append(((x0, y0), (x1, y1)))
                    i = end
                    continue

        elif count == 2:
            end = i + 4 + 2 * 8
            if end <= n:
                px, py = struct.unpack_from("<2d", data, i + 4)
                if _valid_coord(px) and _valid_coord(py):
                    if current:
                        groups.append(current)
                        current = []
                    i = end
                    continue

        elif count == 5:
            end = i + 4 + 5 * 8
            if end <= n:
                vals = struct.unpack_from("<5d", data, i + 4)
                if all(_valid_coord(v) for v in vals):
                    i = end
                    continue

        elif count == 8:
            end = i + 4 + 8 * 8
            if end <= n:
                vals = struct.unpack_from("<8d", data, i + 4)
                if all(_valid_coord(v) for v in vals):
                    i = end
                    continue

        i += 1

    if current:
        groups.append(current)

    return groups


# ── Encadeamento em polígonos ────────────────────────────────────────────────


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _chain_segments_to_polygons(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    tol: float = _DEFAULT_CHAIN_TOL,
    group_label: int | None = None,
) -> list[list[tuple[float, float]]]:
    """Encadeia os segmentos de UM grupo (peça) em polígonos fechados.

    Nunca recebe segmentos de mais de um grupo — o chamador (parse_ads) já
    separou os grupos via _extract_grouped_segments, então o encadeamento
    aqui nunca mistura segmentos de peças diferentes.

    Estende a cadeia em ambas as direções (frente e trás). Arquivos CADZ às
    vezes omitem o lado reto alinhado ao fio/dobra, por isso também fecha
    cadeias abertas com >= 3 segmentos (>= 4 pontos) via segmento implícito.
    Um grupo pode gerar mais de um polígono (ex.: peça com furo interno) —
    todos os candidatos são retornados e filtrados por área depois.
    """
    prefixo = f"[ADS] grupo {group_label}" if group_label is not None else "[ADS]"

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
                if _dist(a, tail) < tol:
                    chain.append(b)
                    used[j] = True
                    found = True
                    break
                elif _dist(b, tail) < tol:
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
                if _dist(b, head) < tol:
                    chain.insert(0, a)
                    used[j] = True
                    found = True
                    break
                elif _dist(a, head) < tol:
                    chain.insert(0, b)
                    used[j] = True
                    found = True
                    break
            if not found:
                break

        fechado = _dist(chain[0], chain[-1]) < tol
        print(
            f"{prefixo} chain start_idx={start_idx}: {len(chain)} pts, "
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
    start_idx: int = 1,
) -> tuple[list[dict[str, Any]], int]:
    """Filtra polígonos por área e retorna no formato geometria_json (GeoJSON Polygon).

    Args:
        start_idx: primeiro número usado em "Peça N", permitindo numeração
            contínua quando chamado várias vezes (uma por grupo).

    Returns:
        (pecas, próximo_start_idx).
    """
    pecas: list[dict[str, Any]] = []
    idx = start_idx

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

    return pecas, idx
