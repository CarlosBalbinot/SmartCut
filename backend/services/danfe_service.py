"""danfe_service.py — Geração de DANFE Simplificada em formato de etiqueta (10x15cm) a partir de NF-e."""

from __future__ import annotations

import re
from io import BytesIO
from typing import Optional

from reportlab.graphics.barcode import code128
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

_PAGE_W, _PAGE_H = 10 * cm, 15 * cm
_MARGEM = 0.3 * cm
_X0 = _MARGEM
_X1 = _PAGE_W - _MARGEM
_LARGURA_UTIL = _X1 - _X0
_CX = _PAGE_W / 2
_PAD_INTERNO = 0.15 * cm

_CINZA_LABEL = colors.HexColor("#f5f5f5")
_BRANCO = colors.white
_PRETO = colors.black

_BORDA_EXTERNA = 1.0
_BORDA_INTERNA = 0.5

_TIPO_LABELS = {"0": "0 - ENTRADA", "1": "1 - SAÍDA"}

# Alturas de cada seção (generosas, com espaçamento entre elas)
_ALT_CABECALHO = 1.0 * cm
_ALT_IDENT = 1.0 * cm
_ALT_CHAVE = 3.6 * cm
_ALT_PROTOCOLO = 1.3 * cm
_ALT_EMITENTE = 1.3 * cm
_ALT_DEST = 1.6 * cm
_GAP = 0  # seções coladas, separadas apenas pela linha de borda


def _formatar_numero_nf(numero: Optional[str]) -> str:
    if not numero:
        return "—"
    digits = re.sub(r"\D", "", str(numero))
    if not digits:
        return "—"
    n = f"{int(digits):09d}"
    return f"{n[:3]}.{n[3:6]}.{n[6:]}"


def _agrupar_chave(chave: str) -> str:
    limpo = "".join(ch for ch in chave if ch.isdigit())
    return " ".join(limpo[i : i + 4] for i in range(0, len(limpo), 4))


def _retangulo(c: canvas.Canvas, x0: float, y0: float, x1: float, y1: float, largura_linha: float, fill=None) -> None:
    if fill is not None:
        c.setFillColor(fill)
        c.rect(x0, y0, x1 - x0, y1 - y0, stroke=0, fill=1)
    c.setStrokeColor(_PRETO)
    c.setLineWidth(largura_linha)
    c.rect(x0, y0, x1 - x0, y1 - y0, stroke=1, fill=0)


def _texto_centralizado(c: canvas.Canvas, texto: str, y_baseline: float, font_name: str, font_size: float) -> None:
    c.setFont(font_name, font_size)
    c.setFillColor(_PRETO)
    c.drawCentredString(_CX, y_baseline, texto)


def _linha_mista(c: canvas.Canvas, segmentos: list, x: float, y: float, tamanho: float) -> None:
    """Desenha uma linha com trechos em negrito e normal, usando drawString +
    stringWidth para calcular o avanço horizontal de cada trecho."""
    cursor_x = x
    for texto, negrito in segmentos:
        fonte = "Helvetica-Bold" if negrito else "Helvetica"
        c.setFont(fonte, tamanho)
        c.setFillColor(_PRETO)
        c.drawString(cursor_x, y, texto)
        cursor_x += c.stringWidth(texto, fonte, tamanho)


def gerar_danfe_simplificada_pdf(dados: dict, empresa=None) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(_PAGE_W, _PAGE_H))

    y_top = _PAGE_H - _MARGEM

    # ── Borda externa envolvendo todas as seções ─────────────────────────────────
    altura_total = _ALT_CABECALHO + _ALT_IDENT + _ALT_CHAVE + _ALT_PROTOCOLO + _ALT_EMITENTE + _ALT_DEST + 5 * _GAP
    _retangulo(c, _X0, y_top - altura_total, _X1, y_top, _BORDA_EXTERNA, fill=_BRANCO)

    # ── 1. Cabeçalho ──────────────────────────────────────────────────────────
    y_bottom = y_top - _ALT_CABECALHO
    _retangulo(c, _X0, y_bottom, _X1, y_top, _BORDA_INTERNA, fill=_BRANCO)
    _texto_centralizado(
        c,
        "DANFE SIMPLIFICADO - ETIQUETA",
        y_bottom + (_ALT_CABECALHO - 10 * 0.7) / 2,
        "Helvetica-Bold",
        10,
    )
    y_top = y_bottom - _GAP

    # ── 2. Linha de identificação ───────────────────────────────────────────────
    y_bottom = y_top - _ALT_IDENT
    _retangulo(c, _X0, y_bottom, _X1, y_top, _BORDA_INTERNA, fill=_BRANCO)
    col_w = _LARGURA_UTIL / 4
    for i in range(1, 4):
        x = _X0 + col_w * i
        c.setStrokeColor(_PRETO)
        c.setLineWidth(_BORDA_INTERNA)
        c.line(x, y_bottom, x, y_top)

    tipo_label = _TIPO_LABELS.get(dados.get("tipo_operacao"), "—")
    data_str = dados["data_emissao"].strftime("%d/%m/%Y") if dados.get("data_emissao") else "—"
    labels = ["NÚMERO", "SÉRIE", "TIPO", "DATA DE EMISSÃO"]
    valores = [_formatar_numero_nf(dados.get("numero_nf")), dados.get("serie") or "—", tipo_label, data_str]
    for i in range(4):
        cx = _X0 + col_w * (i + 0.5)
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(_PRETO)
        c.drawCentredString(cx, y_top - 0.32 * cm, labels[i])
        c.setFont("Helvetica", 8)
        c.drawCentredString(cx, y_bottom + 0.25 * cm, valores[i])
    y_top = y_bottom - _GAP

    # ── 3. Chave de acesso ───────────────────────────────────────────────────────
    y_bottom = y_top - _ALT_CHAVE
    _retangulo(c, _X0, y_bottom, _X1, y_top, _BORDA_INTERNA, fill=_BRANCO)
    chave = dados["chave_acesso"]

    label_row_h = 0.6 * cm
    _retangulo(c, _X0, y_top - label_row_h, _X1, y_top, _BORDA_INTERNA, fill=_CINZA_LABEL)
    _texto_centralizado(c, "CHAVE DE ACESSO", y_top - label_row_h / 2 - 0.09 * cm, "Helvetica-Bold", 7)

    barcode = code128.Code128(chave, barHeight=2.0 * cm, barWidth=0.8, humanReadable=False)
    barcode_x = _CX - barcode.width / 2
    barcode_y = y_top - label_row_h - 0.3 * cm - barcode.height
    barcode.drawOn(c, barcode_x, barcode_y)

    _texto_centralizado(c, _agrupar_chave(chave), barcode_y - 0.3 * cm, "Helvetica", 6)
    y_top = y_bottom - _GAP

    # ── 4. Protocolo de autorização ──────────────────────────────────────────────
    y_bottom = y_top - _ALT_PROTOCOLO
    _retangulo(c, _X0, y_bottom, _X1, y_top, _BORDA_INTERNA, fill=_BRANCO)

    label_row_h = 0.6 * cm
    _retangulo(c, _X0, y_top - label_row_h, _X1, y_top, _BORDA_INTERNA, fill=_CINZA_LABEL)
    _texto_centralizado(
        c,
        "PROTOCOLO DE AUTORIZAÇÃO DE USO",
        y_top - label_row_h / 2 - 0.09 * cm,
        "Helvetica-Bold",
        7,
    )

    protocolo = dados.get("protocolo")
    data_protocolo = dados.get("data_protocolo")
    dh_fmt = data_protocolo.strftime("%d/%m/%Y %H:%M:%S") if data_protocolo else None
    if dh_fmt:
        protocolo_completo = f"{protocolo} {dh_fmt}" if protocolo else dh_fmt
    elif protocolo:
        protocolo_completo = protocolo
    else:
        protocolo_completo = "AGUARDANDO AUTORIZAÇÃO"
    _texto_centralizado(c, protocolo_completo, y_top - label_row_h - 0.35 * cm, "Helvetica", 7)
    y_top = y_bottom - _GAP

    # ── 5. Dados do emitente ─────────────────────────────────────────────────────
    y_bottom = y_top - _ALT_EMITENTE
    _retangulo(c, _X0, y_bottom, _X1, y_top, _BORDA_INTERNA, fill=_BRANCO)
    emit = dados["emitente"]
    x_txt = _X0 + _PAD_INTERNO

    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(_PRETO)
    c.drawString(x_txt, y_top - _PAD_INTERNO - 0.16 * cm, "DADOS DO EMITENTE")

    _linha_mista(
        c,
        [("RAZÃO SOCIAL: ", True), (emit.get("nome") or "—", False)],
        x_txt,
        y_top - _PAD_INTERNO - 0.46 * cm,
        6.5,
    )
    _linha_mista(
        c,
        [
            ("CNPJ: ", True),
            (emit.get("documento") or "—", False),
            ("   IE: ", True),
            (emit.get("ie") or "—", False),
            ("   UF: ", True),
            (emit.get("uf") or "—", False),
        ],
        x_txt,
        y_top - _PAD_INTERNO - 0.76 * cm,
        6.5,
    )
    y_top = y_bottom - _GAP

    # ── 6. Dados do destinatário ─────────────────────────────────────────────────
    y_bottom = y_top - _ALT_DEST
    _retangulo(c, _X0, y_bottom, _X1, y_top, _BORDA_INTERNA, fill=_BRANCO)
    dest = dados["destinatario"]
    x_txt = _X0 + _PAD_INTERNO

    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(_PRETO)
    c.drawString(x_txt, y_top - _PAD_INTERNO - 0.16 * cm, "DADOS DO DESTINATÁRIO")

    _linha_mista(
        c,
        [("NOME: ", True), (dest.get("nome") or "—", False)],
        x_txt,
        y_top - _PAD_INTERNO - 0.46 * cm,
        6.5,
    )
    _linha_mista(
        c,
        [("CPF/CNPJ: ", True), (dest.get("documento") or "—", False)],
        x_txt,
        y_top - _PAD_INTERNO - 0.76 * cm,
        6.5,
    )
    endereco_dest = (
        f"{dest.get('logradouro') or '—'}, {dest.get('numero') or 's/n'} - "
        f"{dest.get('municipio') or '—'}/{dest.get('uf') or '—'} - CEP: {dest.get('cep') or '—'}"
    )
    _linha_mista(
        c,
        [("ENDEREÇO: ", True), (endereco_dest, False)],
        x_txt,
        y_top - _PAD_INTERNO - 1.06 * cm,
        6.5,
    )

    c.showPage()
    c.save()
    return buf.getvalue()
