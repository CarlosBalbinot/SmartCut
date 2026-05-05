import os
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

_CINZA_CLARO = colors.Color(0.94, 0.94, 0.94)
_CINZA_HEADER = colors.Color(0.82, 0.82, 0.82)
_PRETO = colors.black

_N = ParagraphStyle("n", fontName="Helvetica", fontSize=8, leading=10)
_B = ParagraphStyle("b", fontName="Helvetica-Bold", fontSize=8, leading=10)
_S = ParagraphStyle("s", fontName="Helvetica", fontSize=7, leading=9)
_SB = ParagraphStyle("sb", fontName="Helvetica-Bold", fontSize=7, leading=9)
_H = ParagraphStyle("hdr", fontName="Helvetica-Bold", fontSize=8, leading=10, alignment=1)
_BIG = ParagraphStyle("big", fontName="Helvetica-Bold", fontSize=10, leading=13, alignment=2)
_GT = ParagraphStyle("gt", fontName="Helvetica-Bold", fontSize=10, leading=13)


def _brl(v) -> str:
    if v is None:
        return "—"
    s = f"{float(v):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _qty(v) -> str:
    return str(v) if v else ""


def _campo(label: str, valor) -> Paragraph:
    v = valor or "—"
    return Paragraph(f"<b>{label}:</b> {v}", _S)


def _ts_base() -> list:
    return [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# PDF PEDIDO
# ─────────────────────────────────────────────────────────────────────────────

def gerar_pdf_pedido(pedido, itens, empresa) -> bytes:
    tem_plus = any(
        (i.qtd_g1 or 0) + (i.qtd_g2 or 0) + (i.qtd_g3 or 0) > 0
        for i in itens
    )
    page_size = landscape(A4) if tem_plus else A4
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=page_size,
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    w = doc.width
    story = []

    # ── Cabeçalho ────────────────────────────────────────────────────────────
    logo_cell = Paragraph("", _N)
    if empresa and empresa.logo_path and os.path.exists(empresa.logo_path):
        try:
            logo_cell = RLImage(empresa.logo_path, width=40 * mm, height=25 * mm)
        except Exception:
            pass

    emp_lines = []
    if empresa:
        if empresa.razao_social:
            emp_lines.append(Paragraph(empresa.razao_social, _B))
        for txt in filter(None, [
            f"CNPJ: {empresa.cnpj}" if empresa.cnpj else None,
            empresa.endereco,
            " — ".join(filter(None, [empresa.cidade, f"CEP: {empresa.cep}" if empresa.cep else None])),
            f"Tel: {empresa.telefone1}" if empresa.telefone1 else None,
            empresa.email,
        ]):
            emp_lines.append(Paragraph(txt, _S))

    ped_lines = [
        Paragraph(f"<b>PEDIDO Nº:</b> {pedido.numero}", _B),
        Paragraph(f"<b>Data:</b> {pedido.data_emissao.strftime('%d/%m/%Y')}", _S),
        Paragraph(f"<b>Prazo Entrega:</b> {pedido.prazo_entrega_dias or 20} dias", _S),
        Paragraph(f"<b>Condições:</b> {pedido.condicoes or '—'}", _S),
        Paragraph(f"<b>Status:</b> {(pedido.status or 'rascunho').upper()}", _S),
    ]

    hdr_t = Table(
        [[logo_cell, emp_lines, ped_lines]],
        colWidths=[w * 0.18, w * 0.47, w * 0.35],
    )
    hdr_t.setStyle(TableStyle(_ts_base() + [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, _PRETO),
        ("LINEAFTER", (0, 0), (1, 0), 0.3, _CINZA_HEADER),
    ]))
    story.append(hdr_t)
    story.append(Spacer(1, 3 * mm))

    # ── Box cliente ───────────────────────────────────────────────────────────
    cli_t = Table(
        [
            [_campo("RAZÃO SOCIAL", pedido.cliente_razao_social),
             _campo("CNPJ", pedido.cliente_cnpj),
             _campo("I.E.", pedido.cliente_ie)],
            [_campo("ENDEREÇO", pedido.cliente_endereco),
             _campo("CIDADE", pedido.cliente_cidade),
             _campo("CEP", pedido.cliente_cep)],
            [_campo("REPRESENTANTE", pedido.representante),
             _campo("TELEFONE", pedido.cliente_telefone),
             _campo("E-MAIL", pedido.cliente_email)],
        ],
        colWidths=[w * 0.44, w * 0.30, w * 0.26],
    )
    cli_t.setStyle(TableStyle(_ts_base() + [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, _PRETO),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, _CINZA_HEADER),
    ]))
    story.append(cli_t)
    story.append(Spacer(1, 3 * mm))

    # ── Tabela de itens ───────────────────────────────────────────────────────
    if tem_plus:
        hdrs = ["REFERÊNCIA", "COR", "P", "M", "G", "GG", "G1", "G2", "G3", "P.UNIT", "P.TOTAL"]
        col_w = [
            w * 0.22, w * 0.11,
            w * 0.06, w * 0.06, w * 0.06, w * 0.06, w * 0.06, w * 0.06, w * 0.06,
            w * 0.09, w * 0.10,
        ]
    else:
        hdrs = ["REFERÊNCIA", "COR", "P", "M", "G", "GG", "P.UNIT", "P.TOTAL"]
        col_w = [
            w * 0.29, w * 0.17,
            w * 0.08, w * 0.08, w * 0.08, w * 0.08,
            w * 0.10, w * 0.12,
        ]

    rows = [[Paragraph(h, _H) for h in hdrs]]
    for item in itens:
        ref = ""
        if hasattr(item, "grupo") and item.grupo:
            ref = " ".join(filter(None, [item.grupo.codigo, item.grupo.nome]))
        if tem_plus:
            row = [
                Paragraph(ref, _S), Paragraph(item.cor or "", _S),
                _qty(item.qtd_p), _qty(item.qtd_m), _qty(item.qtd_g), _qty(item.qtd_gg),
                _qty(item.qtd_g1), _qty(item.qtd_g2), _qty(item.qtd_g3),
                _brl(item.preco_unitario), _brl(item.preco_total),
            ]
        else:
            row = [
                Paragraph(ref, _S), Paragraph(item.cor or "", _S),
                _qty(item.qtd_p), _qty(item.qtd_m), _qty(item.qtd_g), _qty(item.qtd_gg),
                _brl(item.preco_unitario), _brl(item.preco_total),
            ]
        rows.append(row)

    items_t = Table(rows, colWidths=col_w, repeatRows=1)
    ts = _ts_base() + [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), _CINZA_HEADER),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (-3, -1), "CENTER"),
        ("ALIGN", (-2, 1), (-1, -1), "RIGHT"),
        ("BOX", (0, 0), (-1, -1), 0.5, _PRETO),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.Color(0.82, 0.82, 0.82)),
    ]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            ts.append(("BACKGROUND", (0, i), (-1, i), _CINZA_CLARO))
    items_t.setStyle(TableStyle(ts))
    story.append(items_t)
    story.append(Spacer(1, 3 * mm))

    # ── Rodapé ────────────────────────────────────────────────────────────────
    rod_t = Table(
        [[
            Paragraph("", _N),
            Paragraph(f"<b>Comissão: {_brl(pedido.comissao_valor)}</b>",
                      ParagraphStyle("rc", fontName="Helvetica-Bold", fontSize=10, leading=13, alignment=2)),
            Paragraph(f"<b>TOTAL PEDIDO: {_brl(pedido.total_pedido)}</b>",
                      ParagraphStyle("rt", fontName="Helvetica-Bold", fontSize=11, leading=14, alignment=2)),
        ]],
        colWidths=[w * 0.38, w * 0.30, w * 0.32],
    )
    rod_t.setStyle(TableStyle(_ts_base() + [
        ("BACKGROUND", (0, 0), (-1, -1), _CINZA_CLARO),
        ("BOX", (0, 0), (-1, -1), 0.5, _PRETO),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(rod_t)

    doc.build(story)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# PDF CORTE
# ─────────────────────────────────────────────────────────────────────────────

def gerar_pdf_corte(pedido, itens) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    w = doc.width
    story = []

    story.append(Paragraph(
        f"<b>CORTE — {pedido.cliente_razao_social or 'CLIENTE'} — "
        f"{pedido.data_emissao.strftime('%d/%m/%Y')} — PEDIDO {pedido.numero}</b>",
        _B,
    ))
    story.append(Spacer(1, 5 * mm))

    # Agrupa itens por grupo_id, mantendo ordem por código/nome
    from collections import defaultdict
    grupos_map: dict = {}
    for item in itens:
        gid = str(item.grupo_id)
        if gid not in grupos_map:
            grupos_map[gid] = {"grupo": getattr(item, "grupo", None), "itens": []}
        grupos_map[gid]["itens"].append(item)

    def _sort_key(entry):
        g = entry["grupo"]
        return (g.codigo or "", g.nome or "") if g else ("", "")

    for entry in sorted(grupos_map.values(), key=_sort_key):
        grupo = entry["grupo"]
        g_itens = entry["itens"]

        has_plus = any(
            (i.qtd_g1 or 0) + (i.qtd_g2 or 0) + (i.qtd_g3 or 0) > 0
            for i in g_itens
        )

        titulo = ""
        if grupo:
            titulo = " — ".join(filter(None, [grupo.codigo, grupo.nome]))
        story.append(Paragraph(titulo.upper() or "—", _GT))

        if has_plus:
            col_labels = ["COR", "P", "M", "G", "GG", "G1", "G2", "G3"]
            col_w = [w * 0.30] + [w * 0.10] * 7
        else:
            col_labels = ["COR", "P", "M", "G", "GG"]
            col_w = [w * 0.44] + [w * 0.14] * 4

        rows = [[Paragraph(c, _H) for c in col_labels]]
        for item in g_itens:
            if has_plus:
                row = [
                    Paragraph(item.cor or "", _N),
                    _qty(item.qtd_p), _qty(item.qtd_m),
                    _qty(item.qtd_g), _qty(item.qtd_gg),
                    _qty(item.qtd_g1), _qty(item.qtd_g2), _qty(item.qtd_g3),
                ]
            else:
                row = [
                    Paragraph(item.cor or "", _N),
                    _qty(item.qtd_p), _qty(item.qtd_m),
                    _qty(item.qtd_g), _qty(item.qtd_gg),
                ]
            rows.append(row)

        ts = _ts_base() + [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), _CINZA_HEADER),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.5, _PRETO),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.Color(0.82, 0.82, 0.82)),
        ]
        for i in range(1, len(rows)):
            if i % 2 == 0:
                ts.append(("BACKGROUND", (0, i), (-1, i), _CINZA_CLARO))

        t = Table(rows, colWidths=col_w, repeatRows=1)
        t.setStyle(TableStyle(ts))
        story.append(t)
        story.append(Spacer(1, 5 * mm))

    doc.build(story)
    return buf.getvalue()
