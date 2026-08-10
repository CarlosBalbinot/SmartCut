import os
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

# ── Paleta (preto / branco / cinza claro apenas) ────────────────────────────
_CINZA_CLARO  = colors.Color(0.98, 0.98, 0.98)   # #fafafa — linhas alternadas
_CINZA_LABEL  = colors.Color(0.96, 0.96, 0.96)   # #f5f5f5 — labels do grid cliente / título de grupo
_CINZA_HEADER = colors.Color(0.82, 0.82, 0.82)   # cabeçalho da tabela de corte + linhas finas
_CINZA_ESCURO = colors.Color(0.20, 0.20, 0.20)   # #333 — cabeçalho da tabela de itens do pedido
_PRETO  = colors.black
_BRANCO = colors.white

_N        = ParagraphStyle("n", fontName="Helvetica", fontSize=8, leading=10)
_B        = ParagraphStyle("b", fontName="Helvetica-Bold", fontSize=8, leading=10)
_S        = ParagraphStyle("s", fontName="Helvetica", fontSize=7, leading=9)
_LBL      = ParagraphStyle("lbl", fontName="Helvetica-Bold", fontSize=6, leading=7.5, textColor=colors.Color(0.4, 0.4, 0.4))
_VAL      = ParagraphStyle("val", fontName="Helvetica", fontSize=8.5, leading=11)
_H_ITENS  = ParagraphStyle("hdr_itens", fontName="Helvetica-Bold", fontSize=7.5, leading=9, alignment=1, textColor=_BRANCO)
_H_CORTE  = ParagraphStyle("hdr_corte", fontName="Helvetica-Bold", fontSize=8, leading=10, alignment=1, textColor=_PRETO)
_GT       = ParagraphStyle("gt", fontName="Helvetica-Bold", fontSize=10, leading=18, backColor=_CINZA_LABEL, leftIndent=4)
_CAPTION  = ParagraphStyle("cap", fontName="Helvetica", fontSize=8, leading=10, alignment=1)
_TITULO   = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=13, leading=16)

_COND_LABEL = {"avista": "À Vista", "aprazo": "A Prazo"}

SIZE_COLS = [
    ("P", "qtd_p"), ("M", "qtd_m"), ("G", "qtd_g"), ("GG", "qtd_gg"),
    ("G1", "qtd_g1"), ("G2", "qtd_g2"), ("G3", "qtd_g3"),
]
NORMAL_ATTRS = {"qtd_p", "qtd_m", "qtd_g", "qtd_gg"}
PLUS_ATTRS = {"qtd_g1", "qtd_g2", "qtd_g3"}


def _cond_label(c) -> str:
    return _COND_LABEL.get(c, c or "—")


def _brl(v) -> str:
    if v is None:
        return "—"
    s = f"{float(v):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _qty(v) -> str:
    return str(v) if v else "—"


def _primeiro_nome(razao_social) -> str:
    if not razao_social or not razao_social.strip():
        return "Cliente"
    return razao_social.strip().split()[0].capitalize()


def _numero_fmt(numero) -> str:
    try:
        return f"{int(numero):06d}"
    except (TypeError, ValueError):
        return str(numero or "").zfill(6)


def nome_arquivo_pedido(pedido) -> str:
    return f"{_primeiro_nome(pedido.cliente_razao_social)}-pedido{_numero_fmt(pedido.numero)}.pdf"


def nome_arquivo_corte(pedido) -> str:
    return f"CORTE-{_primeiro_nome(pedido.cliente_razao_social)}-pedido{_numero_fmt(pedido.numero)}.pdf"


def _ts_base() -> list:
    return [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]


def _grid_row(cells, total_w) -> Table:
    """Uma linha do grid de dados do cliente: label com fundo cinza claro
    em cima, valor embaixo. `cells` é uma lista de (label, valor, peso)."""
    col_w = [total_w * peso for _, _, peso in cells]
    labels = [Paragraph(label, _LBL) for label, _, _ in cells]
    valores = [Paragraph(str(valor) if valor not in (None, "") else "—", _VAL) for _, valor, _ in cells]
    t = Table([labels, valores], colWidths=col_w)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _CINZA_LABEL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, _PRETO),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, _PRETO),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, 0), 2),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ("TOPPADDING", (0, 1), (-1, 1), 1.5),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 3),
    ]))
    return t


def _tamanho_valores(item, cols, only=None) -> list:
    """Valores das colunas de tamanho para uma linha. Se `only` for um set
    de nomes de atributo, colunas fora dele aparecem como '—' (usado para
    separar a linha de tamanhos normais da linha de plus size)."""
    out = []
    for _, attr in cols:
        if only is None or attr in only:
            out.append(_qty(getattr(item, attr, 0)))
        else:
            out.append("—")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# PDF PEDIDO
# ─────────────────────────────────────────────────────────────────────────────

def gerar_pdf_pedido(pedido, itens, empresa, precos_ref=None) -> bytes:
    """precos_ref: dict opcional {str(grupo_id): PrecoReferencia} usado para
    saber quais referências têm plus size e obter o preço plus da tabela."""
    precos_ref = precos_ref or {}

    ativos = [(lbl, attr) for lbl, attr in SIZE_COLS if any(getattr(i, attr, 0) for i in itens)]
    tem_plus_cols = any(attr in PLUS_ATTRS for _, attr in ativos)
    n_size = max(len(ativos), 1)

    page_size = landscape(A4) if tem_plus_cols else A4
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=page_size,
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    w = doc.width
    story = []

    # ── Cabeçalho: logo (30%) | empresa (40%) | box do pedido (30%) ──────────
    logo_cell = Paragraph("", _N)
    if empresa and empresa.logo_path and os.path.exists(empresa.logo_path):
        try:
            logo_cell = RLImage(empresa.logo_path, width=38 * mm, height=24 * mm)
        except Exception:
            pass

    emp_lines = []
    if empresa:
        if empresa.razao_social:
            emp_lines.append(Paragraph(empresa.razao_social, _B))
        linha_end = " — ".join(filter(None, [
            empresa.endereco,
            f"CEP: {empresa.cep}" if empresa.cep else None,
            empresa.cidade,
        ]))
        if linha_end:
            emp_lines.append(Paragraph(linha_end, _S))
        linha_contato = " — ".join(filter(None, [
            f"Fone: {empresa.telefone1}" if empresa.telefone1 else None,
            f"CNPJ: {empresa.cnpj}" if empresa.cnpj else None,
            empresa.email,
            empresa.site,
        ]))
        if linha_contato:
            emp_lines.append(Paragraph(linha_contato, _S))

    ped_lines = [
        Paragraph(f"<b>PEDIDO Nº:</b> {pedido.numero}", _B),
        Paragraph(f"<b>Data:</b> {pedido.data_emissao.strftime('%d/%m/%Y')}", _S),
        Paragraph(f"<b>Prazo Entrega:</b> {pedido.prazo_entrega_dias or 20} dias", _S),
        Paragraph(f"<b>Condições:</b> {_cond_label(pedido.condicoes)}", _S),
        Paragraph(f"<b>Representante:</b> {pedido.representante or '—'}", _S),
    ]

    hdr_t = Table(
        [[logo_cell, emp_lines, ped_lines]],
        colWidths=[w * 0.30, w * 0.40, w * 0.30],
    )
    hdr_t.setStyle(TableStyle(_ts_base() + [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.6, _PRETO),
        ("LINEAFTER", (0, 0), (0, 0), 0.4, _PRETO),
        ("LINEAFTER", (1, 0), (1, 0), 0.4, _PRETO),
        ("BOX", (2, 0), (2, 0), 0.6, _PRETO),
    ]))
    story.append(hdr_t)
    story.append(Spacer(1, 3 * mm))

    # ── Dados do cliente (grid de 5 linhas) ───────────────────────────────────
    story.append(_grid_row([
        ("CLIENTE/RAZÃO SOCIAL", pedido.cliente_razao_social, 0.60),
        ("CNPJ", pedido.cliente_cnpj, 0.25),
        ("I.E.", pedido.cliente_ie, 0.15),
    ], w))
    story.append(_grid_row([
        ("ENDEREÇO", pedido.cliente_endereco, 0.60),
        ("CONDIÇÕES", _cond_label(pedido.condicoes), 0.40),
    ], w))
    story.append(_grid_row([
        ("CIDADE", pedido.cliente_cidade, 0.40),
        ("CEP", pedido.cliente_cep, 0.20),
        ("PRAZO ENTR.", f"{pedido.prazo_entrega_dias or 20} dias", 0.20),
        ("FONE", pedido.cliente_telefone, 0.20),
    ], w))
    story.append(_grid_row([
        ("CONTATO", None, 0.50),
        ("E-MAIL", pedido.cliente_email, 0.50),
    ], w))
    story.append(_grid_row([
        ("OBS", pedido.observacoes, 1.0),
    ], w))
    story.append(Spacer(1, 4 * mm))

    # ── Tabela de itens ────────────────────────────────────────────────────────
    hdrs = ["REFERÊNCIA", "NOME DA PEÇA", "COR"] + [lbl for lbl, _ in ativos] + ["P.UNIT", "P.TOTAL"]
    fixo_w = w * 0.10 + w * 0.20 + w * 0.10  # referência + nome + cor
    preco_w = w * 0.09 + w * 0.10            # p.unit + p.total
    size_w = (w - fixo_w - preco_w) / n_size
    col_w = [w * 0.10, w * 0.20, w * 0.10] + [size_w] * len(ativos) + [w * 0.09, w * 0.10]

    rows = [[Paragraph(h, _H_ITENS) for h in hdrs]]
    row_groups = []
    plus_rows = []
    grupo_idx = 0

    for item in itens:
        codigo = item.grupo.codigo if getattr(item, "grupo", None) else ""
        nome = item.grupo.nome if getattr(item, "grupo", None) else ""
        cor = item.cor or ""

        pref = precos_ref.get(str(item.grupo_id))
        tem_plus_ref = bool(pref and pref.tem_plus_size)
        qty_plus = (item.qtd_g1 or 0) + (item.qtd_g2 or 0) + (item.qtd_g3 or 0)

        if tem_plus_ref and qty_plus > 0:
            qty_normal = (item.qtd_p or 0) + (item.qtd_m or 0) + (item.qtd_g or 0) + (item.qtd_gg or 0)
            preco_normal = item.preco_unitario
            subtotal_normal = Decimal(str(preco_normal or 0)) * qty_normal

            preco_plus = pref.preco_avista_plus if pedido.condicoes == "avista" else pref.preco_aprazo_plus
            subtotal_plus = Decimal(str(preco_plus or 0)) * qty_plus

            linha1 = [Paragraph(codigo, _S), Paragraph(nome, _S), Paragraph(cor, _S)] \
                + _tamanho_valores(item, ativos, only=NORMAL_ATTRS) \
                + [_brl(preco_normal), _brl(subtotal_normal)]
            linha2 = [Paragraph(codigo, _S), Paragraph(nome, _S), Paragraph(cor, _S)] \
                + _tamanho_valores(item, ativos, only=PLUS_ATTRS) \
                + [_brl(preco_plus), _brl(subtotal_plus)]

            rows.append(linha1); row_groups.append(grupo_idx)
            rows.append(linha2); row_groups.append(grupo_idx)
            plus_rows.append(len(rows) - 1)
        else:
            linha = [Paragraph(codigo, _S), Paragraph(nome, _S), Paragraph(cor, _S)] \
                + _tamanho_valores(item, ativos) \
                + [_brl(item.preco_unitario), _brl(item.preco_total)]
            rows.append(linha); row_groups.append(grupo_idx)

        grupo_idx += 1

    n_fixed_left = 3
    size_end = n_fixed_left + len(ativos) - 1

    items_t = Table(rows, colWidths=col_w, repeatRows=1)
    ts = _ts_base() + [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), _CINZA_ESCURO),
        ("TEXTCOLOR", (0, 0), (-1, 0), _BRANCO),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ALIGN", (n_fixed_left, 0), (size_end, -1), "CENTER"),
        ("ALIGN", (-2, 1), (-1, -1), "RIGHT"),
        ("BOX", (0, 0), (-1, -1), 0.5, _PRETO),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, _CINZA_HEADER),
    ]
    for i in range(1, len(rows)):
        if row_groups[i - 1] % 2 == 1:
            ts.append(("BACKGROUND", (0, i), (-1, i), _CINZA_CLARO))
    for idx in plus_rows:
        ts.append(("LINEABOVE", (0, idx), (-1, idx), 0, _BRANCO))
    items_t.setStyle(TableStyle(ts))
    story.append(items_t)
    story.append(Spacer(1, 3 * mm))

    # ── Rodapé (comissão + total) ─────────────────────────────────────────────
    rod_t = Table(
        [[
            Paragraph(f"Comissão: {_brl(pedido.comissao_valor)}",
                      ParagraphStyle("rc", fontName="Helvetica-Bold", fontSize=9, leading=12)),
            Paragraph(f"TOTAL PEDIDO: {_brl(pedido.total_pedido)}",
                      ParagraphStyle("rt", fontName="Helvetica-Bold", fontSize=11, leading=14, alignment=2)),
        ]],
        colWidths=[w * 0.5, w * 0.5],
    )
    rod_t.setStyle(TableStyle(_ts_base() + [
        ("BACKGROUND", (0, 0), (-1, -1), _CINZA_CLARO),
        ("BOX", (0, 0), (-1, -1), 0.5, _PRETO),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(rod_t)

    # ── Assinaturas ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 14 * mm))
    assinaturas = Table(
        [
            [HRFlowable(width="88%", thickness=0.7, color=_PRETO),
             HRFlowable(width="88%", thickness=0.7, color=_PRETO)],
            [Paragraph("Cliente", _CAPTION), Paragraph("Representante", _CAPTION)],
        ],
        colWidths=[w * 0.5, w * 0.5],
    )
    assinaturas.setStyle(TableStyle(_ts_base() + [
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
    ]))
    story.append(assinaturas)

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

    primeiro = _primeiro_nome(pedido.cliente_razao_social)
    story.append(Paragraph(f"CORTE — {primeiro}", _TITULO))
    story.append(Paragraph(f"Data: {pedido.data_emissao.strftime('%d/%m/%Y')}", _N))
    story.append(Paragraph(f"Cliente: {pedido.cliente_razao_social or '—'}", _N))
    story.append(Spacer(1, 6 * mm))

    # Agrupa itens por grupo_id, mantendo ordem por código/nome
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

        ativos = [(lbl, attr) for lbl, attr in SIZE_COLS if any(getattr(i, attr, 0) for i in g_itens)]
        if not ativos:
            continue

        if grupo and grupo.codigo:
            titulo = f"{grupo.nome} — REF: {grupo.codigo}"
        else:
            titulo = grupo.nome if grupo else "—"
        story.append(Paragraph(titulo.upper(), _GT))
        story.append(Spacer(1, 1.5 * mm))

        col_labels = ["COR"] + [lbl for lbl, _ in ativos]
        cor_w = w * 0.28
        size_w = (w - cor_w) / len(ativos)
        col_w = [cor_w] + [size_w] * len(ativos)

        rows = [[Paragraph(c, _H_CORTE) for c in col_labels]]
        row_groups = []
        plus_rows = []
        grupo_idx = 0

        for item in g_itens:
            qty_plus = (item.qtd_g1 or 0) + (item.qtd_g2 or 0) + (item.qtd_g3 or 0)
            qty_normal = (item.qtd_p or 0) + (item.qtd_m or 0) + (item.qtd_g or 0) + (item.qtd_gg or 0)

            if qty_plus > 0 and qty_normal > 0:
                linha1 = [Paragraph(item.cor or "", _N)] + _tamanho_valores(item, ativos, only=NORMAL_ATTRS)
                linha2 = [Paragraph(item.cor or "", _N)] + _tamanho_valores(item, ativos, only=PLUS_ATTRS)
                rows.append(linha1); row_groups.append(grupo_idx)
                rows.append(linha2); row_groups.append(grupo_idx)
                plus_rows.append(len(rows) - 1)
            else:
                linha = [Paragraph(item.cor or "", _N)] + _tamanho_valores(item, ativos)
                rows.append(linha); row_groups.append(grupo_idx)

            grupo_idx += 1

        ts = _ts_base() + [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), _CINZA_HEADER),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.5, _PRETO),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, _CINZA_HEADER),
        ]
        for i in range(1, len(rows)):
            if row_groups[i - 1] % 2 == 1:
                ts.append(("BACKGROUND", (0, i), (-1, i), _CINZA_CLARO))
        for idx in plus_rows:
            ts.append(("LINEABOVE", (0, idx), (-1, idx), 0, _BRANCO))

        t = Table(rows, colWidths=col_w, repeatRows=1)
        t.setStyle(TableStyle(ts))
        story.append(t)
        story.append(Spacer(1, 5 * mm))

    doc.build(story)
    return buf.getvalue()
