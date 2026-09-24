"""report_service.py — Geração de relatórios PDF (pedido e encaixe)."""

from __future__ import annotations

import math
from datetime import date
from io import BytesIO
from typing import Any

from reportlab.graphics.shapes import (
    Drawing,
    Line as GLine,
    Polygon as GPoly,
    Rect as GRect,
    String as GStr,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Cores ─────────────────────────────────────────────────────────────────────

_AZUL        = colors.HexColor("#1e40af")
_AZUL_MEDIO  = colors.HexColor("#2563eb")
_AZUL_CLARO  = colors.HexColor("#dbeafe")
_AZUL_FUNDO  = colors.HexColor("#eff6ff")
_CINZA_HEADER= colors.HexColor("#f1f5f9")
_CINZA_BORDA = colors.HexColor("#e2e8f0")
_VERDE       = colors.HexColor("#166534")
_VERDE_CLARO = colors.HexColor("#dcfce7")
_TEXTO       = colors.HexColor("#1e293b")
_MUTED       = colors.HexColor("#64748b")
_BRANCO      = colors.white

# Paleta para os moldes no desenho (15 cores distintas)
_PALETTE_HEX = [
    "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
    "#ec4899", "#14b8a6", "#f97316", "#6366f1", "#84cc16",
    "#06b6d4", "#a855f7", "#f43f5e", "#22c55e", "#eab308",
]

_STATUS_LABEL = {
    "rascunho":    "Rascunho",
    "processando": "Em produção",
    "concluido":   "Concluído",
    "cancelado":   "Cancelado",
}

_TIPO_LABEL = {
    "simples":         "Simples",
    "par":             "Par ↔",
    "par_sem_espelho": "Par s/↔",
}

# ── Dimensões de página ───────────────────────────────────────────────────────

_PAGE_W, _PAGE_H = A4
_LM = _RM = 1.8 * cm        # margens laterais
_TM = 1.8 * cm              # margem superior
_BM = 1.4 * cm              # margem inferior (menor para rodapé)
_UW = _PAGE_W - _LM - _RM  # largura útil ≈ 493 pts


# ══════════════════════════════════════════════════════════════════════════════
# Helpers de geometria
# ══════════════════════════════════════════════════════════════════════════════

def _rotate_poly(polygon: list, deg: float) -> list:
    """Rotação anti-horária padrão (mesma convenção do nest_worker.js)."""
    if not deg:
        return list(polygon)
    rad = math.radians(deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    return [(x * cos_a - y * sin_a, x * sin_a + y * cos_a) for x, y in polygon]


def _bbox_min(polygon: list) -> tuple[float, float]:
    return min(p[0] for p in polygon), min(p[1] for p in polygon)


def _centroid(polygon: list) -> tuple[float, float]:
    n = len(polygon)
    return (sum(p[0] for p in polygon) / n,
            sum(p[1] for p in polygon) / n)


def _world_polygon(polygon: list, px: float, py: float, rot: float) -> list:
    """Reconstrói as coordenadas absolutas do polígono no espaço do tecido.

    O worker salva (x, y) como o canto inferior-esquerdo do bbox rotacionado.
    """
    rotated = _rotate_poly(polygon, rot)
    min_x, min_y = _bbox_min(rotated)
    ox, oy = px - min_x, py - min_y
    return [(x + ox, y + oy) for x, y in rotated]


def _aggregate_pieces(placements: list) -> list[dict]:
    """Agrega os placements por molde_id somando contagens."""
    bucket: dict[str, dict] = {}
    for pl in placements:
        mid = str(pl.get("id", "?"))
        if mid not in bucket:
            bucket[mid] = {
                "id":        mid,
                "grupo_nome": pl.get("grupo_nome") or "—",
                "peca":      pl.get("peca")      or "—",
                "tamanho":   pl.get("tamanho")   or "—",
                "count":     0,
            }
        bucket[mid]["count"] += 1
    return sorted(bucket.values(), key=lambda x: (x["grupo_nome"], x["peca"], x["tamanho"]))


def _fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ══════════════════════════════════════════════════════════════════════════════
# Drawing ReportLab do mapa de encaixe
# ══════════════════════════════════════════════════════════════════════════════

def _encaixe_drawing(mapa: dict) -> Drawing:
    """Cria um Drawing ReportLab com os polígonos posicionados em escala."""
    largura_cm     = float(mapa.get("largura_cm", 150))
    comprimento_cm = float(mapa.get("comprimento_cm", 100))
    placements     = mapa.get("placements", [])

    # Escala: cabe na largura útil, altura máx 14 cm
    MAX_H_PTS = 14.0 * cm
    scale = min(_UW / largura_cm, MAX_H_PTS / comprimento_cm)

    dw = largura_cm     * scale   # largura do desenho em pts
    dh = comprimento_cm * scale   # altura  do desenho em pts

    # Offset para centralizar o tecido na largura útil
    x_off = (_UW - dw) / 2.0

    d = Drawing(_UW, dh)

    # ── Fundo do tecido ──────────────────────────────────────────────────────
    d.add(GRect(x_off, 0, dw, dh,
                fillColor=colors.HexColor("#f0f7ff"),
                strokeColor=colors.HexColor("#60a5fa"),
                strokeWidth=1.0))

    # ── Linhas de referência a cada 50 cm (ao longo do comprimento) ──────────
    y_cm = 50.0
    while y_cm < comprimento_cm:
        rl_y = dh - y_cm * scale
        d.add(GLine(x_off, rl_y, x_off + dw, rl_y,
                    strokeColor=colors.HexColor("#bfdbfe"),
                    strokeWidth=0.35))
        d.add(GStr(x_off + 2, rl_y + 2, f"{int(y_cm)} cm",
                   fontSize=5.5, fillColor=colors.HexColor("#93c5fd"),
                   textAnchor="start"))
        y_cm += 50.0

    # ── Borda superior (início do corte) ─────────────────────────────────────
    d.add(GLine(x_off, dh, x_off + dw, dh,
                strokeColor=colors.HexColor("#3b82f6"), strokeWidth=1.0))

    # ── Polígonos das peças ───────────────────────────────────────────────────
    color_map: dict[str, int] = {}
    c_idx = 0

    for pl in placements:
        poly = pl.get("polygon")
        if not poly or len(poly) < 3:
            continue

        mid = str(pl.get("id", ""))
        if mid not in color_map:
            color_map[mid] = c_idx % len(_PALETTE_HEX)
            c_idx += 1

        hex_c  = _PALETTE_HEX[color_map[mid]]
        base_c = colors.HexColor(hex_c)
        fill_c = colors.Color(base_c.red, base_c.green, base_c.blue, alpha=0.4)

        world = _world_polygon(
            poly,
            float(pl.get("x", 0)),
            float(pl.get("y", 0)),
            float(pl.get("rotation", 0)),
        )

        # y invertido: nesting y-down → ReportLab y-up
        pts = []
        for wx, wy in world:
            pts.append(x_off + wx * scale)
            pts.append(dh    - wy * scale)

        if len(pts) < 6:
            continue

        d.add(GPoly(pts, fillColor=fill_c, strokeColor=base_c, strokeWidth=0.8))

        # Label (tamanho ou parte da peça)
        label = pl.get("tamanho") or pl.get("peca") or ""
        if label:
            cx, cy = _centroid(world)
            rl_cx = x_off + cx * scale
            rl_cy = dh    - cy * scale
            fs = max(5.0, min(9.0, scale * 3.5))
            d.add(GStr(rl_cx, rl_cy - fs * 0.5, label,
                       fontSize=fs,
                       fillColor=colors.HexColor("#0f172a"),
                       textAnchor="middle"))

    # ── Dimensão da largura no topo ───────────────────────────────────────────
    d.add(GLine(x_off, dh + 3, x_off + dw, dh + 3,
                strokeColor=colors.HexColor("#93c5fd"), strokeWidth=0.5))
    d.add(GStr(x_off + dw / 2, dh + 5,
               f"← {largura_cm:.0f} cm →",
               fontSize=6.5, fillColor=colors.HexColor("#3b82f6"),
               textAnchor="middle"))

    return d


# ══════════════════════════════════════════════════════════════════════════════
# Helpers de tabela
# ══════════════════════════════════════════════════════════════════════════════

def _base_ts() -> list:
    return [
        ("BACKGROUND",    (0, 0), (-1,  0), _CINZA_HEADER),
        ("TEXTCOLOR",     (0, 0), (-1,  0), _MUTED),
        ("FONTNAME",      (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.4, _CINZA_BORDA),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [_BRANCO, colors.HexColor("#f8fafc")]),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]


def _instr_cell(label: str, value: str) -> Paragraph:
    return Paragraph(
        f'<font name="Helvetica" size="7" color="#2563eb">{label}</font><br/>'
        f'<font name="Helvetica-Bold" size="17" color="#1e40af">{value}</font>',
        ParagraphStyle("ICell", alignment=1, leading=22, spaceAfter=0),
    )


def _p_muted(text: str) -> Paragraph:
    return Paragraph(
        text,
        ParagraphStyle("Muted", fontName="Helvetica", fontSize=8,
                       textColor=_MUTED, spaceAfter=0),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Rodapé de página
# ══════════════════════════════════════════════════════════════════════════════

def _make_footer(num_pedido: str):
    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(_MUTED)
        y = _BM * 0.45
        canvas.drawString(_LM, y, f"Página {doc.page}")
        canvas.drawCentredString(_PAGE_W / 2, y, f"Pedido {num_pedido}")
        canvas.drawRightString(_PAGE_W - _RM, y,
                               f"SmartCut • {date.today().strftime('%d/%m/%Y')}")
        canvas.restoreState()
    return _footer


# ══════════════════════════════════════════════════════════════════════════════
# PDF do Encaixe — relatório de corte com desenho
# ══════════════════════════════════════════════════════════════════════════════

def gerar_pdf_encaixe(pedido: dict, encaixes: list[dict[str, Any]]) -> bytes:
    """Gera PDF de relatório de corte com mapa visual de cada enfesto.

    Args:
        pedido:  dict com num_pedido, cliente, data_pedido, etc.
        encaixes: lista de EncaixeOut.model_dump() com mapa_json enriquecido.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=_LM,
        rightMargin=_RM,
        topMargin=_TM,
        bottomMargin=_BM + 0.6 * cm,  # espaço para rodapé
    )

    story: list = []

    # ── Estilos ──────────────────────────────────────────────────────────────
    st_h1 = ParagraphStyle(
        "EH1", fontName="Helvetica-Bold", fontSize=22,
        textColor=_AZUL, spaceAfter=2, leading=26,
    )
    st_sub = ParagraphStyle(
        "ESub", fontName="Helvetica", fontSize=10,
        textColor=_MUTED, spaceAfter=0,
    )
    st_secao_tit = ParagraphStyle(
        "ESecTit", fontName="Helvetica-Bold", fontSize=12,
        textColor=_BRANCO, spaceBefore=0, spaceAfter=0, leading=15,
    )
    st_normal = ParagraphStyle(
        "ENorm", fontName="Helvetica", fontSize=9, textColor=_TEXTO,
    )
    st_rodape_label = ParagraphStyle(
        "ERodLabel", fontName="Helvetica", fontSize=7, textColor=_MUTED,
        alignment=1, leading=9,
    )
    st_rodape_val = ParagraphStyle(
        "ERodVal", fontName="Helvetica-Bold", fontSize=11, textColor=_AZUL,
        alignment=1, leading=14,
    )

    num_pedido = pedido.get("num_pedido", "—")

    # ── Cabeçalho ────────────────────────────────────────────────────────────
    hoje = date.today().strftime("%d/%m/%Y")
    cabecalho_data = [[
        Paragraph("SmartCut", st_h1),
        Paragraph(
            f'<font name="Helvetica-Bold" color="#1e40af">RELATÓRIO DE ENCAIXE</font><br/>'
            f'<font name="Helvetica" size="9" color="#64748b">'
            f'Gerado em {hoje}</font>',
            ParagraphStyle("EHR", alignment=2, leading=14),
        ),
    ]]
    cab_table = Table(cabecalho_data, colWidths=[_UW * 0.55, _UW * 0.45])
    cab_table.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(cab_table)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=_AZUL, spaceAfter=8))

    # Dados do pedido
    cliente = pedido.get("cliente") or "—"
    data_ped = pedido.get("data_pedido") or "—"
    info_data = [[
        Paragraph(
            f'<font name="Helvetica" size="8" color="#64748b">PEDIDO</font><br/>'
            f'<font name="Helvetica-Bold" size="13" color="#1e293b">{num_pedido}</font>',
            ParagraphStyle("PI", leading=16),
        ),
        Paragraph(
            f'<font name="Helvetica" size="8" color="#64748b">CLIENTE</font><br/>'
            f'<font name="Helvetica-Bold" size="13" color="#1e293b">{cliente}</font>',
            ParagraphStyle("PC", leading=16),
        ),
        Paragraph(
            f'<font name="Helvetica" size="8" color="#64748b">DATA DO PEDIDO</font><br/>'
            f'<font name="Helvetica-Bold" size="13" color="#1e293b">{data_ped}</font>',
            ParagraphStyle("PD", leading=16),
        ),
    ]]
    info_table = Table(info_data, colWidths=[_UW * 0.3, _UW * 0.4, _UW * 0.3])
    info_table.setStyle(TableStyle([
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 10))

    # ── Cards de resumo geral ─────────────────────────────────────────────────
    total_m   = sum(float(e.get("comp_metros")  or 0) for e in encaixes)
    total_kg  = sum(float(e.get("peso_kg")      or 0) for e in encaixes)
    total_brl = sum(float(e.get("custo_total")  or 0) for e in encaixes)
    aprov_med = (
        sum(100 - float(e.get("desperdicio_pct") or 0) for e in encaixes)
        / len(encaixes)
        if encaixes else 0
    )

    def _card_cell(label: str, value: str, destaque: bool = False) -> Paragraph:
        cor_val = "#1e40af" if destaque else "#1e293b"
        return Paragraph(
            f'<font name="Helvetica" size="7" color="#64748b">{label}</font><br/>'
            f'<font name="Helvetica-Bold" size="13" color="{cor_val}">{value}</font>',
            ParagraphStyle("Card", alignment=1, leading=16),
        )

    n_enf = len(encaixes)
    summary_data = [[
        _card_cell("ENFESTOS",     str(n_enf)),
        _card_cell("METROS TOTAIS", f"{total_m:.2f} m"),
        _card_cell("PESO TOTAL",    f"{total_kg:.3f} kg"),
        _card_cell("CUSTO TOTAL",   _fmt_brl(total_brl), destaque=True),
        _card_cell("APROVEITAMENTO", f"{aprov_med:.1f}%",
                   destaque=(aprov_med >= 75)),
    ]]
    n_cols = 5
    summary_table = Table(summary_data, colWidths=[_UW / n_cols] * n_cols)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), _AZUL_FUNDO),
        ("BOX",           (0,0), (-1,-1), 0.8, _AZUL_CLARO),
        ("INNERGRID",     (0,0), (-1,-1), 0.4, _AZUL_CLARO),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 14))

    # ── Seção por enfesto ─────────────────────────────────────────────────────
    for idx, enc in enumerate(encaixes, start=1):
        mapa        = enc.get("mapa_json") or {}
        placements  = mapa.get("placements", [])
        tecido_nome = mapa.get("tecido_nome") or "Tecido"
        largura_cm  = float(mapa.get("largura_cm") or 0)
        comp_m      = float(enc.get("comp_metros") or 0)
        peso_kg     = float(enc.get("peso_kg")     or 0)
        custo       = float(enc.get("custo_total") or 0)
        n_camadas   = int(enc.get("num_camadas")   or 1)
        desp_pct    = float(enc.get("desperdicio_pct") or 0)
        aprov_pct   = 100.0 - desp_pct

        # ── Título do enfesto ────────────────────────────────────────────────
        titulo_data = [[
            Paragraph(
                f"ENFESTO {idx}",
                ParagraphStyle("EN", fontName="Helvetica-Bold", fontSize=9,
                               textColor=colors.HexColor("#93c5fd"), leading=11),
            ),
            Paragraph(
                tecido_nome.upper(),
                ParagraphStyle("ET", fontName="Helvetica-Bold", fontSize=13,
                               textColor=_BRANCO, leading=15),
            ),
            Paragraph(
                f"Aproveitamento: {aprov_pct:.1f}%",
                ParagraphStyle("EA", fontName="Helvetica-Bold", fontSize=9,
                               textColor=colors.HexColor("#93c5fd"),
                               alignment=2, leading=11),
            ),
        ]]
        titulo_table = Table(titulo_data, colWidths=[_UW * 0.18, _UW * 0.52, _UW * 0.30])
        titulo_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), _AZUL),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING",   (0,0), (-1,-1), 12),
            ("RIGHTPADDING",  (0,0), (-1,-1), 12),
            ("TOPPADDING",    (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ]))

        # ── Box de instruções ────────────────────────────────────────────────
        larg_str = f"{largura_cm:.0f} cm" if largura_cm else "—"
        instr_data = [[
            _instr_cell("CAMADAS",           str(n_camadas)),
            _instr_cell("COMPRIMENTO",       f"{comp_m:.2f} m"),
            _instr_cell("LARGURA DO TECIDO", larg_str),
            _instr_cell("PESO",              f"{peso_kg:.3f} kg"),
        ]]
        instr_table = Table(instr_data, colWidths=[_UW / 4] * 4)
        instr_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), _AZUL_CLARO),
            ("BOX",           (0,0), (-1,-1), 0.6, _AZUL),
            ("INNERGRID",     (0,0), (-1,-1), 0.4, _AZUL_CLARO),
            ("ALIGN",         (0,0), (-1,-1), "CENTER"),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ]))

        # ── Tabela de peças ──────────────────────────────────────────────────
        pieces = _aggregate_pieces(placements)

        pec_rows: list = [["Grupo / Modelo", "Parte", "Tamanho", "Qtd. no plano"]]
        for p in pieces:
            pec_rows.append([
                p["grupo_nome"],
                p["peca"],
                p["tamanho"],
                f"{p['count']} peça{'s' if p['count'] != 1 else ''}",
            ])

        pec_table = Table(
            pec_rows,
            colWidths=[_UW * 0.40, _UW * 0.25, _UW * 0.15, _UW * 0.20],
            repeatRows=1,
        )
        pec_table.setStyle(TableStyle(
            _base_ts() + [("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold")]
        ))

        # Junta título + box instrução em bloco indivisível
        story.append(KeepTogether([titulo_table, instr_table]))
        story.append(Spacer(1, 6))

        if pieces:
            story.append(
                Paragraph(
                    "PEÇAS A CORTAR NESTE ENFESTO",
                    ParagraphStyle("PLabel", fontName="Helvetica-Bold", fontSize=7.5,
                                   textColor=_MUTED, spaceBefore=0, spaceAfter=4,
                                   letterSpacing=0.8),
                )
            )
            story.append(pec_table)
        elif placements:
            story.append(_p_muted("(metadados de peças não disponíveis neste encaixe)"))

        # ── Desenho do encaixe ───────────────────────────────────────────────
        story.append(Spacer(1, 8))
        if placements and any(pl.get("polygon") for pl in placements):
            story.append(
                Paragraph(
                    "MAPA DE ENCAIXE",
                    ParagraphStyle("MapLabel", fontName="Helvetica-Bold", fontSize=7.5,
                                   textColor=_MUTED, spaceBefore=0, spaceAfter=4,
                                   letterSpacing=0.8),
                )
            )
            story.append(_encaixe_drawing(mapa))
        else:
            story.append(_p_muted("(desenho do encaixe não disponível — execute o nesting para gerar)"))

        # ── Barra de totais do enfesto ───────────────────────────────────────
        story.append(Spacer(1, 8))
        stats_data = [[
            Paragraph(
                f'<font name="Helvetica" size="7" color="#64748b">APROVEITAMENTO</font><br/>'
                f'<font name="Helvetica-Bold" size="11" '
                f'color="{"#166534" if aprov_pct >= 75 else "#92400e"}">{aprov_pct:.1f}%</font>',
                ParagraphStyle("S1", alignment=1, leading=14),
            ),
            Paragraph(
                f'<font name="Helvetica" size="7" color="#64748b">COMPRIMENTO ENFESTO</font><br/>'
                f'<font name="Helvetica-Bold" size="11" color="#1e40af">{comp_m:.2f} m</font>',
                ParagraphStyle("S2", alignment=1, leading=14),
            ),
            Paragraph(
                f'<font name="Helvetica" size="7" color="#64748b">PESO TECIDO</font><br/>'
                f'<font name="Helvetica-Bold" size="11" color="#1e40af">{peso_kg:.3f} kg</font>',
                ParagraphStyle("S3", alignment=1, leading=14),
            ),
            Paragraph(
                f'<font name="Helvetica" size="7" color="#64748b">CUSTO</font><br/>'
                f'<font name="Helvetica-Bold" size="11" color="#1e40af">{_fmt_brl(custo)}</font>',
                ParagraphStyle("S4", alignment=1, leading=14),
            ),
        ]]
        stats_table = Table(stats_data, colWidths=[_UW / 4] * 4)
        stats_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), _CINZA_HEADER),
            ("BOX",           (0,0), (-1,-1), 0.5, _CINZA_BORDA),
            ("INNERGRID",     (0,0), (-1,-1), 0.3, _CINZA_BORDA),
            ("ALIGN",         (0,0), (-1,-1), "CENTER"),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ]))
        story.append(stats_table)

        # Separador entre enfestos
        if idx < len(encaixes):
            story.append(Spacer(1, 18))
            story.append(HRFlowable(width="100%", thickness=0.5,
                                    color=_CINZA_BORDA, spaceAfter=14))

    # ── Rodapé de totais ──────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=1.5, color=_AZUL, spaceAfter=10))

    totais_row = [[
        Paragraph(
            f'<font name="Helvetica" size="8" color="#64748b">TOTAL DE ENFESTOS</font><br/>'
            f'<font name="Helvetica-Bold" size="14" color="#1e40af">{len(encaixes)}</font>',
            ParagraphStyle("T1", alignment=1, leading=17),
        ),
        Paragraph(
            f'<font name="Helvetica" size="8" color="#64748b">METROS TOTAIS</font><br/>'
            f'<font name="Helvetica-Bold" size="14" color="#1e40af">{total_m:.2f} m</font>',
            ParagraphStyle("T2", alignment=1, leading=17),
        ),
        Paragraph(
            f'<font name="Helvetica" size="8" color="#64748b">PESO TOTAL</font><br/>'
            f'<font name="Helvetica-Bold" size="14" color="#1e40af">{total_kg:.3f} kg</font>',
            ParagraphStyle("T3", alignment=1, leading=17),
        ),
        Paragraph(
            f'<font name="Helvetica" size="8" color="#64748b">CUSTO TOTAL</font><br/>'
            f'<font name="Helvetica-Bold" size="16" color="#1e40af">{_fmt_brl(total_brl)}</font>',
            ParagraphStyle("T4", alignment=1, leading=19),
        ),
        Paragraph(
            f'<font name="Helvetica" size="8" color="#64748b">APROVEITAMENTO MÉDIO</font><br/>'
            f'<font name="Helvetica-Bold" size="14" '
            f'color="{"#166534" if aprov_med >= 75 else "#92400e"}">'
            f'{aprov_med:.1f}%</font>',
            ParagraphStyle("T5", alignment=1, leading=17),
        ),
    ]]
    totais_table = Table(totais_row, colWidths=[_UW / 5] * 5)
    totais_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), _AZUL_FUNDO),
        ("BOX",           (0,0), (-1,-1), 1.0, _AZUL),
        ("INNERGRID",     (0,0), (-1,-1), 0.4, _AZUL_CLARO),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
    ]))
    story.append(totais_table)

    footer = _make_footer(num_pedido)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


# ── Stub legado ───────────────────────────────────────────────────────────────

def gerar_pdf(encaixe: Any) -> dict:
    raise NotImplementedError(
        "Use gerar_pdf_encaixe(pedido, encaixes) para relatório de encaixe."
    )
