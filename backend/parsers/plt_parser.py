"""Parser para arquivos PLT/HPGL com suporte ao formato PE (Polyline Encoded).

O formato PE usado por sistemas CAD de moda (Lectra, Gerber etc.) codifica
coordenadas com inteiros de comprimento variável onde:
  - bytes 63-126 (0x3F-0x7E): grupo não-terminal, valor = byte - 63 (6 bits)
  - bytes 128-254 (0x80-0xFE): grupo terminal, valor = byte - 191 (6 bits)
  - bytes 59-62: controle (<>=;)

Cada valor é montado juntando grupos LSB-first e depois decodificado via
zigzag (par → positivo, ímpar → negativo).

Separadores dentro do stream PE:
  - '<=' (0x3C 0x3D): posição absoluta (pen-down)

Unidades: 1016 unidades/polegada → 400 unidades/cm.
"""

from __future__ import annotations

from typing import Any

from shapely.geometry import Polygon

PLT_TO_CM = 1.0 / (1016 / 2.54)  # ≈ 1/400


def parse_plt(caminho: str) -> list[dict[str, Any]]:
    """Extrai peças de arquivo PLT (HP-GL/2 com PE encoding).

    Returns:
        Lista de dicts com {nome_sugerido, geometria_json, area_cm2}.
    """
    with open(caminho, "rb") as f:
        data = f.read()

    pe_start = data.find(b"PE")
    if pe_start == -1:
        return _parse_plt_textual(data)

    pe_data = data[pe_start + 2 :]
    polylines = _decode_pe(pe_data)
    return _polylines_to_pecas(polylines)


# ── Decodificador PE ────────────────────────────────────────────────────────


def _decode_pe(data: bytes) -> list[list[tuple[float, float]]]:
    """Decodifica stream HP-GL/2 PE e retorna lista de polylines em cm."""

    # Localiza todos os marcadores '<=' (pen-down absoluto)
    abs_markers: list[int] = []
    for i in range(len(data) - 1):
        if data[i] == 0x3C and data[i + 1] == 0x3D:
            abs_markers.append(i + 2)  # posição após '<='

    if not abs_markers:
        return []

    polylines: list[list[tuple[float, float]]] = []

    for m_idx, start in enumerate(abs_markers):
        end = abs_markers[m_idx + 1] - 2 if m_idx + 1 < len(abs_markers) else len(data)
        seg = data[start:end]

        coords = _decode_coords(seg)
        pts = _coords_to_points(coords)
        if pts:
            polylines.append(pts)

    return polylines


def _decode_coords(seg: bytes) -> list[int]:
    """Converte segmento de bytes PE em lista de inteiros (zigzag-decodificados)."""
    coords: list[int] = []
    current_groups: list[int] = []

    for b in seg:
        if b >= 128:  # byte terminal (alto)
            val = b - 191
            current_groups.append(val)
            # monta valor a partir dos grupos LSB-first
            v = 0
            for j, bits in enumerate(current_groups):
                v |= bits << (6 * j)
            # zigzag decode
            coords.append(-(v >> 1) - 1 if (v & 1) else v >> 1)
            current_groups = []
        elif 63 <= b <= 126:  # byte não-terminal (normal)
            current_groups.append(b - 63)
        # bytes < 63 são ignorados (control chars residuais)

    return coords


def _coords_to_points(coords: list[int]) -> list[tuple[float, float]]:
    """Converte lista de inteiros (x_abs, y_abs, dx, dy, ...) em pontos em cm."""
    if len(coords) < 2:
        return []

    # Primeiro par: posição absoluta
    x = coords[0]
    y = coords[1]
    pts: list[tuple[float, float]] = [(x * PLT_TO_CM, y * PLT_TO_CM)]

    i = 2
    while i + 1 < len(coords):
        x += coords[i]
        y += coords[i + 1]
        pts.append((x * PLT_TO_CM, y * PLT_TO_CM))
        i += 2

    return pts


# ── Classificação e geração de peças ────────────────────────────────────────


def _polylines_to_pecas(polylines: list[list[tuple[float, float]]]) -> list[dict[str, Any]]:
    """Filtra polylines fechadas com área significativa e retorna peças."""
    MIN_AREA_CM2 = 20.0  # ignora marcas, entalhes
    MAX_AREA_CM2 = 5000.0  # ignora retângulo de moldura do plot

    pecas: list[dict[str, Any]] = []
    idx = 1

    for pts in polylines:
        if len(pts) < 3:
            continue

        # Verifica se é fechada (último ponto ≈ primeiro)
        dist = ((pts[0][0] - pts[-1][0]) ** 2 + (pts[0][1] - pts[-1][1]) ** 2) ** 0.5
        is_closed = dist < 0.5  # < 0.5 cm de distância

        if not is_closed:
            continue

        try:
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            area = float(poly.area)
        except Exception:
            continue

        if not (MIN_AREA_CM2 <= area <= MAX_AREA_CM2):
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


# ── Fallback: PLT textual (PU/PD) ───────────────────────────────────────────


def _parse_plt_textual(data: bytes) -> list[dict[str, Any]]:
    """Fallback para arquivos PLT com comandos PU/PD textuais."""
    PLT_TO_CM_TEXT = 1 / 400.0

    texto = data.decode("latin-1", errors="replace")
    comandos = texto.replace("\n", "").replace("\r", "").split(";")

    pecas: list[dict[str, Any]] = []
    contorno: list[tuple[float, float]] = []
    caneta_baixa = False
    idx = 1

    def _extrair(s: str) -> list[tuple[float, float]]:
        nums = [n.strip() for n in s.split(",") if n.strip()]
        out = []
        for i in range(0, len(nums) - 1, 2):
            try:
                out.append((float(nums[i]) * PLT_TO_CM_TEXT, float(nums[i + 1]) * PLT_TO_CM_TEXT))
            except ValueError:
                pass
        return out

    def _salvar():
        nonlocal idx
        if len(contorno) < 3:
            return
        poly = Polygon(contorno)
        if not poly.is_valid:
            poly = poly.buffer(0)
        coords_list = [list(p) for p in poly.exterior.coords]
        pecas.append(
            {
                "nome_sugerido": f"Peça {idx}",
                "geometria_json": {"type": "Polygon", "coordinates": [coords_list]},
                "area_cm2": round(float(poly.area), 4),
            }
        )
        idx += 1

    for cmd in comandos:
        cmd = cmd.strip()
        if not cmd:
            continue
        upper = cmd.upper()
        if upper.startswith("PD"):
            caneta_baixa = True
            contorno.extend(_extrair(cmd[2:]))
        elif upper.startswith("PU"):
            if caneta_baixa:
                _salvar()
            caneta_baixa = False
            contorno = list(_extrair(cmd[2:]))

    if caneta_baixa:
        _salvar()

    return pecas
