"""contabilidade_service.py — Geração do pacote contábil mensal (ZIP + PDFs de resumo)."""

from __future__ import annotations

import os
import re
import zipfile
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

MESES_NOME = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

_PRETO = colors.black
_BRANCO = colors.white
_CINZA_TXT = colors.Color(0.4, 0.4, 0.4)
_CINZA_HEADER = colors.Color(0.85, 0.85, 0.85)
_CINZA_CLARO = colors.Color(0.97, 0.97, 0.97)

_INVALID_CHARS = re.compile(r'[\\/:*?"<>|]')


def _mes_nome(mes: int) -> str:
    return MESES_NOME[mes - 1] if 1 <= mes <= 12 else str(mes)


def _brl(v) -> str:
    if v is None:
        return "—"
    s = f"{float(v):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _data_fmt(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


def _dec_sum(itens: list[dict], chave: str) -> Decimal:
    total = Decimal("0")
    for item in itens:
        total += Decimal(str(item.get(chave) or 0))
    return total


def _sanitize_nome_arquivo(nome: str) -> str:
    limpo = _INVALID_CHARS.sub("-", (nome or "").strip())
    return limpo or "arquivo"


# ── PDF de Resumo (dentro do pacote ZIP) ───────────────────────────────────────

_ts_base = [
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
]

_N     = ParagraphStyle("cs_n", fontName="Helvetica", fontSize=8, leading=10)
_N_R   = ParagraphStyle("cs_n_r", fontName="Helvetica", fontSize=8, leading=10, alignment=2)
_S     = ParagraphStyle("cs_s", fontName="Helvetica", fontSize=8, leading=10, textColor=_CINZA_TXT)
_B     = ParagraphStyle("cs_b", fontName="Helvetica-Bold", fontSize=9, leading=11)
_TITULO = ParagraphStyle("cs_titulo", fontName="Helvetica-Bold", fontSize=14, leading=17)
_H_SECAO = ParagraphStyle("cs_h_secao", fontName="Helvetica-Bold", fontSize=10, leading=13)
_H_TAB  = ParagraphStyle("cs_h_tab", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=_BRANCO)
_TOTAL_SECAO = ParagraphStyle("cs_total_secao", fontName="Helvetica-Bold", fontSize=8.5, leading=11, alignment=2)


def _tabela_style() -> TableStyle:
    return TableStyle(_ts_base + [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), _CINZA_TXT),
        ("TEXTCOLOR", (0, 0), (-1, 0), _BRANCO),
        ("BOX", (0, 0), (-1, -1), 0.5, _PRETO),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, _CINZA_HEADER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_BRANCO, _CINZA_CLARO]),
    ])


def gerar_resumo_pdf(dados: dict, empresa=None) -> bytes:
    """Resumo-{MES}-{ANO}.pdf incluído dentro do pacote ZIP contábil."""
    mes, ano = dados["mes"], dados["ano"]
    mes_nome = _mes_nome(mes).upper()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
    )
    w = doc.width
    story: list = []

    # ── Cabeçalho ──────────────────────────────────────────────────────────────
    logo_cell = Paragraph("", _N)
    if empresa and getattr(empresa, "logo_path", None) and os.path.exists(empresa.logo_path):
        try:
            logo_cell = RLImage(empresa.logo_path, width=26 * mm, height=17 * mm)
        except Exception:
            pass

    titulo_cell = [
        Paragraph(f"DOCUMENTOS CONTÁBEIS — {mes_nome} {ano}", _TITULO),
        Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y')}", _S),
    ]
    hdr = Table([[logo_cell, titulo_cell]], colWidths=[w * 0.20, w * 0.80])
    hdr.setStyle(TableStyle(_ts_base + [("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(hdr)
    story.append(Spacer(1, 2 * mm))
    story.append(HRFlowable(width="100%", thickness=0.8, color=_PRETO))
    story.append(Spacer(1, 6 * mm))

    total_docs = 0

    # ── Seção 1: Notas Fiscais de Venda ──────────────────────────────────────────
    story.append(Paragraph("NOTAS FISCAIS DE VENDA", _H_SECAO))
    story.append(Spacer(1, 2 * mm))
    notas_venda = dados["notas_venda"]
    if notas_venda:
        rows = [[Paragraph(h, _H_TAB) for h in ["Cliente", "NF", "Data", "Valor"]]]
        for v in notas_venda:
            rows.append([
                Paragraph(v["cliente"] or "—", _N),
                Paragraph(v.get("numero_nf") or "—", _N),
                Paragraph(_data_fmt(v["data_venda"]), _N),
                Paragraph(_brl(v["valor_total"]), _N_R),
            ])
        t = Table(rows, colWidths=[w * 0.42, w * 0.16, w * 0.18, w * 0.24], repeatRows=1)
        t.setStyle(_tabela_style())
        story.append(t)
    else:
        story.append(Paragraph("Nenhuma nota de venda no período.", _S))
    story.append(Spacer(1, 1.5 * mm))
    story.append(Paragraph(f"Total da seção: {_brl(_dec_sum(notas_venda, 'valor_total'))}", _TOTAL_SECAO))
    story.append(Spacer(1, 6 * mm))
    total_docs += len(notas_venda)

    # ── Seção 2: Notas Fiscais de Compra ─────────────────────────────────────────
    story.append(Paragraph("NOTAS FISCAIS DE COMPRA", _H_SECAO))
    story.append(Spacer(1, 2 * mm))
    notas_compra = dados["notas_compra"]
    if notas_compra:
        rows = [[Paragraph(h, _H_TAB) for h in ["Fornecedor", "NF", "Data", "Valor"]]]
        for c in notas_compra:
            rows.append([
                Paragraph(c["fornecedor"] or "—", _N),
                Paragraph(c.get("numero_nf") or "—", _N),
                Paragraph(_data_fmt(c["data_compra"]), _N),
                Paragraph(_brl(c["valor_total"]), _N_R),
            ])
        t = Table(rows, colWidths=[w * 0.42, w * 0.16, w * 0.18, w * 0.24], repeatRows=1)
        t.setStyle(_tabela_style())
        story.append(t)
    else:
        story.append(Paragraph("Nenhuma nota de compra no período.", _S))
    story.append(Spacer(1, 1.5 * mm))
    story.append(Paragraph(f"Total da seção: {_brl(_dec_sum(notas_compra, 'valor_total'))}", _TOTAL_SECAO))
    story.append(Spacer(1, 6 * mm))
    total_docs += len(notas_compra)

    # ── Seção 3: Boletos Pagos ────────────────────────────────────────────────────
    story.append(Paragraph("BOLETOS PAGOS", _H_SECAO))
    story.append(Spacer(1, 2 * mm))
    boletos = dados["boletos_pagos"]
    if boletos:
        rows = [[Paragraph(h, _H_TAB) for h in ["Fornecedor/Cliente", "NF", "Parcela", "Data Pagto", "Valor"]]]
        for b in boletos:
            parcela = (
                f"{b['parcela_numero']}/{b['parcela_total']}"
                if b.get("parcela_numero") and b.get("parcela_total") else "Único"
            )
            rows.append([
                Paragraph(b["fornecedor_cliente"] or "—", _N),
                Paragraph(b.get("numero_nf") or "—", _N),
                Paragraph(parcela, _N),
                Paragraph(_data_fmt(b["data_pagamento"]), _N),
                Paragraph(_brl(b["valor"]), _N_R),
            ])
        t = Table(rows, colWidths=[w * 0.34, w * 0.14, w * 0.14, w * 0.16, w * 0.22], repeatRows=1)
        t.setStyle(_tabela_style())
        story.append(t)
    else:
        story.append(Paragraph("Nenhum boleto pago no período.", _S))
    story.append(Spacer(1, 1.5 * mm))
    story.append(Paragraph(f"Total da seção: {_brl(_dec_sum(boletos, 'valor'))}", _TOTAL_SECAO))
    story.append(Spacer(1, 8 * mm))
    total_docs += len(boletos)

    # ── Rodapé ─────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.6, color=_PRETO))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(f"Total de documentos: {total_docs}", _B))
    story.append(Spacer(1, 1 * mm))
    story.append(HRFlowable(width="100%", thickness=0.3, color=_CINZA_HEADER))
    story.append(Spacer(1, 2 * mm))
    rodape_empresa = " — ".join(filter(None, [
        empresa.razao_social if empresa else None,
        f"CNPJ: {empresa.cnpj}" if empresa and empresa.cnpj else None,
    ]))
    story.append(Paragraph(rodape_empresa or "—", _S))

    doc.build(story)
    return buf.getvalue()


# ── PDF de Resumo Interno (minimalista, download avulso) ───────────────────────

_TITULO_INT   = ParagraphStyle("ci_titulo", fontName="Helvetica-Bold", fontSize=13, leading=16)
_SUB_INT      = ParagraphStyle("ci_sub", fontName="Helvetica", fontSize=9, leading=12, textColor=_CINZA_TXT)
_H_SECAO_INT  = ParagraphStyle("ci_h_secao", fontName="Helvetica-Bold", fontSize=9.5, leading=13)
_LINHA        = ParagraphStyle("ci_linha", fontName="Helvetica", fontSize=8.5, leading=11)
_LINHA_B      = ParagraphStyle("ci_linha_b", fontName="Helvetica-Bold", fontSize=9, leading=12)
_VALOR        = ParagraphStyle("ci_valor", fontName="Helvetica", fontSize=8.5, leading=11, alignment=2)
_VALOR_B      = ParagraphStyle("ci_valor_b", fontName="Helvetica-Bold", fontSize=9, leading=12, alignment=2)
_VALOR_CINZA  = ParagraphStyle("ci_valor_cinza", fontName="Helvetica", fontSize=8.5, leading=11, alignment=2, textColor=_CINZA_TXT)
_LABEL_CINZA  = ParagraphStyle("ci_label_cinza", fontName="Helvetica", fontSize=8.5, leading=11, textColor=_CINZA_TXT)
_N_CINZA      = ParagraphStyle("ci_n_cinza", fontName="Helvetica-Oblique", fontSize=8, leading=10, textColor=_CINZA_TXT)


def _linha_valor(w: float, label: str, valor, negrito: bool = False, cinza: bool = False) -> Table:
    if cinza:
        label_style, valor_style = _LABEL_CINZA, _VALOR_CINZA
    elif negrito:
        label_style, valor_style = _LINHA_B, _VALOR_B
    else:
        label_style, valor_style = _LINHA, _VALOR
    t = Table(
        [[Paragraph(label, label_style), Paragraph(_brl(valor), valor_style)]],
        colWidths=[w - 32 * mm, 32 * mm],
    )
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    return t


def gerar_resumo_interno_pdf(dados: dict, empresa=None) -> bytes:
    """PDF minimalista (preto e branco) de uso interno — sem anexos, apenas números."""
    mes, ano = dados["mes"], dados["ano"]
    mes_nome = _mes_nome(mes)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
    )
    w = doc.width
    story: list = []

    story.append(Paragraph(f"RESUMO FINANCEIRO — {mes_nome.upper()} {ano}", _TITULO_INT))
    if empresa and getattr(empresa, "razao_social", None):
        story.append(Paragraph(empresa.razao_social, _SUB_INT))
    story.append(Spacer(1, 2 * mm))
    story.append(HRFlowable(width="100%", thickness=0.7, color=_PRETO))
    story.append(Spacer(1, 4 * mm))

    notas_venda = dados["notas_venda"]
    notas_compra = dados["notas_compra"]
    boletos = dados["boletos_pagos"]

    total_vendas = _dec_sum(notas_venda, "valor_total")
    total_compras = _dec_sum(notas_compra, "valor_total")
    total_pago = _dec_sum(boletos, "valor")

    # ── Vendas do mês ────────────────────────────────────────────────────────────
    story.append(Paragraph("VENDAS DO MÊS", _H_SECAO_INT))
    story.append(Spacer(1, 1.5 * mm))
    if notas_venda:
        for v in notas_venda:
            label = f"{v['cliente']} — NF {v.get('numero_nf') or '—'}"
            story.append(_linha_valor(w, label, v["valor_total"]))
    else:
        story.append(Paragraph("Nenhuma venda com NF no período.", _N_CINZA))
    story.append(Spacer(1, 1 * mm))
    story.append(_linha_valor(w, "Total Vendas", total_vendas, negrito=True))
    story.append(Spacer(1, 4 * mm))

    # ── Compras do mês ───────────────────────────────────────────────────────────
    story.append(Paragraph(f"COMPRAS DO MÊS (NFs emitidas em {mes_nome})", _H_SECAO_INT))
    story.append(Spacer(1, 1.5 * mm))
    if notas_compra:
        for c in notas_compra:
            label = f"{c['fornecedor']} — NF {c.get('numero_nf') or '—'}"
            story.append(_linha_valor(w, label, c["valor_total"]))
    else:
        story.append(Paragraph("Nenhuma compra com NF no período.", _N_CINZA))
    story.append(Spacer(1, 1 * mm))
    story.append(_linha_valor(w, "Total Compras", total_compras, negrito=True))
    story.append(Spacer(1, 4 * mm))

    # ── Boletos pagos no mês ─────────────────────────────────────────────────────
    story.append(Paragraph(f"BOLETOS PAGOS EM {mes_nome.upper()}", _H_SECAO_INT))
    story.append(Spacer(1, 1.5 * mm))
    if boletos:
        for b in boletos:
            if b.get("parcela_numero") and b.get("parcela_total"):
                parcela = f" - Parcela {b['parcela_numero']}/{b['parcela_total']}"
            else:
                parcela = ""
            label = f"{b['fornecedor_cliente']} - NF {b.get('numero_nf') or '—'}{parcela}"
            story.append(_linha_valor(w, label, b["valor"]))
    else:
        story.append(Paragraph("Nenhum boleto pago no período.", _N_CINZA))
    story.append(Spacer(1, 1 * mm))
    story.append(_linha_valor(w, "Total Pago", total_pago, negrito=True))
    story.append(Spacer(1, 5 * mm))

    # ── Resultado ────────────────────────────────────────────────────────────────
    resultado = total_vendas - total_compras
    story.append(HRFlowable(width="100%", thickness=0.7, color=_PRETO))
    story.append(Spacer(1, 3 * mm))
    story.append(_linha_valor(w, "Receitas", total_vendas, cinza=True))
    story.append(_linha_valor(w, "Despesas", total_compras, cinza=True))
    story.append(Spacer(1, 1 * mm))
    story.append(_linha_valor(w, "Resultado", resultado, negrito=True))

    doc.build(story)
    return buf.getvalue()


# ── Pacote ZIP contábil ──────────────────────────────────────────────────────────

def montar_pacote_zip(dados: dict, empresa=None) -> bytes:
    mes, ano = dados["mes"], dados["ano"]
    pasta_raiz = f"Contabilidade-{mes:02d}-{ano}"

    buf = BytesIO()
    contagem: dict[str, int] = {}

    def _nome_unico(caminho_zip: str) -> str:
        if caminho_zip not in contagem:
            contagem[caminho_zip] = 0
            return caminho_zip
        contagem[caminho_zip] += 1
        base, ext = os.path.splitext(caminho_zip)
        return f"{base} ({contagem[caminho_zip]}){ext}"

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:

        def _add_arquivo(subpasta: str, nome_base: str, caminho_disco: Optional[str]) -> None:
            if not caminho_disco or not os.path.exists(caminho_disco):
                return
            ext = os.path.splitext(caminho_disco)[1] or ".pdf"
            nome = _sanitize_nome_arquivo(nome_base) + ext
            caminho_zip = _nome_unico(f"{pasta_raiz}/{subpasta}/{nome}")
            zf.write(caminho_disco, caminho_zip)

        for v in dados["notas_venda"]:
            nome = f"{v['cliente']}-NF{v.get('numero_nf') or 'SN'}"
            _add_arquivo("1-Notas-de-Venda", nome, v.get("nf_pdf_path"))

        for c in dados["notas_compra"]:
            nome = f"{c['fornecedor']}-NF{c.get('numero_nf') or 'SN'}"
            _add_arquivo("2-Notas-de-Compra", nome, c.get("nf_pdf_path"))

        for b in dados["boletos_pagos"]:
            base = f"{b['fornecedor_cliente']}-NF{b.get('numero_nf') or 'SN'}"
            if b.get("parcela_numero") and b.get("parcela_total"):
                nome_boleto = f"{base}-Parcela{b['parcela_numero']}de{b['parcela_total']}"
            else:
                nome_boleto = f"{base}-Boleto"
            _add_arquivo("3-Boletos-Pagos", nome_boleto, b.get("boleto_pdf_path"))
            _add_arquivo("3-Boletos-Pagos", f"{base}-NotaFiscal", b.get("nf_pdf_path"))

        resumo_pdf = gerar_resumo_pdf(dados, empresa)
        zf.writestr(f"{pasta_raiz}/Resumo-{mes:02d}-{ano}.pdf", resumo_pdf)

    return buf.getvalue()
