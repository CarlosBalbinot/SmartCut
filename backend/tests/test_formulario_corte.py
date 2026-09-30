"""Formulário de corte — services/relatorios/dados_ordem_corte.

Desenho da mesa deitado e visto do cortador (largura na horizontal com
"INÍCIO DA MESA" embaixo, comprimento na vertical — encaixe girado 180°,
nunca espelhado), campo ENFESTO e o tipo de enfesto com padrão MESMA_FACE.
Funções puras: não precisa de banco.
"""

import re

import pytest

from services.relatorios.dados_ordem_corte import _pontos_tela, desenho_svg, enfesto_texto, tipo_enfesto

# Mesa da OC-0003: tecido de 150 cm, mesa de 87 cm, uma peça de 40 × 80 cm
# no canto (x = largura, y = comprimento).
MAPA = {
    "largura_cm": 150.0,
    "comprimento_cm": 87.0,
    "placements": [
        {
            "id": "m1",
            "x": 0.0,
            "y": 0.0,
            "rotation": 0,
            "polygon": [[0, 0], [40, 0], [40, 80], [0, 80]],
            "peca": "COSTAS",
            "tamanho": "M",
        },
        {
            "id": "m2",
            "x": 50.0,
            "y": 0.0,
            "rotation": 0,
            "polygon": [[0, 0], [40, 0], [40, 80], [0, 80]],
            "peca": "COSTAS",
            "tamanho": "M",
            "espelhada": True,
        },
    ],
}


def _tecido(svg: str) -> tuple[float, float, float, float]:
    """(x, y, largura, altura) do retângulo do tecido, em mm."""
    m = re.search(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"', svg)
    assert m, svg
    return tuple(float(v) for v in m.groups())


def test_desenho_deitado_largura_na_horizontal():
    svg = str(desenho_svg(MAPA))
    _, _, w, h = _tecido(svg)
    # 150 cm de largura na horizontal, 87 cm de comprimento na vertical.
    assert w > h
    assert abs(w / h - 150 / 87) < 0.01


def test_desenho_cotas_e_inicio_da_mesa():
    svg = str(desenho_svg(MAPA))
    _, y, _, h = _tecido(svg)
    largura = re.search(r'<text x="[\d.]+" y="([\d.]+)">150 cm</text>', svg)
    comprimento = re.search(r'transform="rotate\(-90[^"]*"\s*>87 cm</text>', svg)
    inicio = re.search(r'y="([\d.]+)"[^>]*>INÍCIO DA MESA</text>', svg)
    assert largura and float(largura.group(1)) > y + h  # cota da largura embaixo
    assert comprimento  # cota do comprimento na vertical, à esquerda
    # "INÍCIO DA MESA" embaixo, logo abaixo da cota da largura
    assert inicio and float(inicio.group(1)) > float(largura.group(1))
    assert 'fill="#777"' in svg


def _svg_mm(svg: str) -> tuple[float, float]:
    m = re.search(r'<svg[^>]* width="([\d.]+)mm" height="([\d.]+)mm"', svg)
    assert m, svg
    return float(m.group(1)), float(m.group(2))


def test_desenho_escala_fixa_150cm_100mm():
    _, _, w, _ = _tecido(str(desenho_svg(MAPA)))
    assert abs(w - 100.0) < 0.05  # 150 cm de tecido ≈ 100 mm, sem esticar


def test_desenho_limite_110_x_90_mantendo_proporcao():
    comprida = {**MAPA, "comprimento_cm": 200.0}
    svg = str(desenho_svg(comprida))
    largura_mm, altura_mm = _svg_mm(svg)
    assert largura_mm <= 110.0 + 0.05 and altura_mm <= 90.0 + 0.05
    _, _, w, h = _tecido(svg)
    assert abs(w / h - 150 / 200) < 0.01
    larga = {**MAPA, "largura_cm": 200.0}
    assert _svg_mm(str(desenho_svg(larga)))[0] <= 110.0 + 0.05


def test_desenho_fontes_em_pt():
    svg = str(desenho_svg(MAPA))
    nomes = [float(v) for v in re.findall(r'<text font-size="([\d.]+)"', svg)]
    assert nomes and all(5 * 0.3528 - 0.01 <= f <= 8 * 0.3528 + 0.01 for f in nomes)  # 5 a 8 pt
    cotas = re.findall(r'font-size="([\d.]+)"[^>]*>(?:<text[^>]*>)?(?:150 cm|INÍCIO DA MESA)', svg)
    assert cotas and all(abs(float(f) - 7 * 0.3528) < 0.01 for f in cotas)  # 7 pt


def test_desenho_espelhada_tracejada_e_nomes():
    svg = str(desenho_svg(MAPA))
    assert svg.count("stroke-dasharray") == 1
    assert "(esp.)" in svg
    assert svg.count(">COSTAS M</tspan>") == 2


def test_desenho_sem_dados():
    assert str(desenho_svg({})) == ""
    assert str(desenho_svg({"largura_cm": 150, "comprimento_cm": 0, "placements": []})) == ""


def test_enfesto_texto():
    assert enfesto_texto("FACE_A_FACE", 6) == "Face a face · 6 camadas"
    assert enfesto_texto("MESMA_FACE", 5) == "Face única · 5 camadas"
    assert enfesto_texto("MESMA_FACE", 1) == "Face única · 1 camada"


def test_tipo_enfesto_padrao_mesma_face():
    assert tipo_enfesto(None) == "MESMA_FACE"
    assert tipo_enfesto({}) == "MESMA_FACE"
    assert tipo_enfesto({"tipo_enfesto": "OUTRO"}) == "MESMA_FACE"
    assert tipo_enfesto({"tipo_enfesto": "face_a_face"}) == "FACE_A_FACE"


# ── Giro de 180° (nunca espelho) ─────────────────────────────────────────

# Peça assimétrica conhecida ("L"), longe dos cantos da mesa
L = [[0, 0], [30, 0], [30, 10], [10, 10], [10, 60], [0, 60]]
MAPA_L = {
    "largura_cm": 150.0,
    "comprimento_cm": 87.0,
    "placements": [{"id": "l", "x": 12.0, "y": 7.0, "rotation": 0, "polygon": L, "peca": "BOLSO", "tamanho": "M"}],
}


def _area_assinada(pts):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1])) / 2


def _desenhado_cm(svg: str) -> list[tuple[float, float]]:
    """Polígono da peça no SVG, de volta para cm no referencial da tela."""
    x0, y0, w, _ = _tecido(svg)
    escala = w / MAPA_L["largura_cm"]
    pontos = re.search(r'<polygon points="([^"]+)"', svg).group(1).split()
    return [((float(px) - x0) / escala, (float(py) - y0) / escala) for px, py in (p.split(",") for p in pontos)]


def test_desenho_gira_180_sem_espelhar():
    anterior = _pontos_tela(MAPA_L["placements"][0])  # desenho anterior (início da mesa em cima)
    girado = [(150.0 - x, 87.0 - y) for x, y in anterior]
    desenhado = _desenhado_cm(str(desenho_svg(MAPA_L)))
    # é o desenho anterior girado 180° ...
    assert all(abs(a - b) < 0.05 and abs(c - d) < 0.05 for (a, c), (b, d) in zip(desenhado, girado))
    # ... com a mesma orientação (espelhar um eixo só inverteria o sinal da área)
    assert _area_assinada(desenhado) * _area_assinada(anterior) > 0
    espelhado_x = [(150.0 - x, y) for x, y in anterior]
    espelhado_y = [(x, 87.0 - y) for x, y in anterior]
    assert _area_assinada(desenhado) * _area_assinada(espelhado_x) < 0
    assert _area_assinada(desenhado) * _area_assinada(espelhado_y) < 0


def test_desenho_inicio_da_mesa_embaixo():
    # O início da mesa (y = 0 no motor) fica na borda de BAIXO: a peça que o
    # motor pôs perto do início aparece na parte de baixo do desenho.
    desenhado = _desenhado_cm(str(desenho_svg(MAPA_L)))
    assert max(y for _, y in desenhado) == pytest.approx(87.0 - 7.0, abs=0.05)
