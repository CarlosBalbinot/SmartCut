"""Fonte de dados do relPro001 (Formulário de corte da Ordem de Corte ou do
Encaixe Rápido — este sem OC, pelo id do pedido do encaixe).

Mesmo contrato do relVen001 (dados_pedido): só tipos simples (dict/list/
str/Decimal/date) — o modelo roda em sandbox. A única exceção é o desenho
da mesa (mesas[].desenho_svg, enfestos[].desenho_svg e o antigo
enfestos[].miniatura_svg, que aponta para o mesmo desenho), gerado aqui a
partir do mapa_json e marcado como seguro (Markup): o modelo não escreve
JavaScript nem SVG.

Chaves: empresa, oc, pedido, grades, enfestos, grupos, mesas, produtos,
totais (a engine acrescenta "impressao").

produtos[] (OC organizada por PRODUTO, encaixes do plano de corte): a ficha
por produto — uma seção por produto, e dentro dela uma por tecido, com a
grade cor × tamanho do pedido e as mesas daquele produto na ordem de corte.
Vazio quando a OC é por COR (a ficha continua pela lista mesas[]). mesas[] alimenta o formulário do cortador
(relPro001.html) e o formulário básico (relPro001_basico.html);
enfestos/grupos/grades ficam para variantes personalizadas.

Mesa × enfesto (M2c): cada encaixe é uma MESA (parte do enfesto) e lista os
MOLDES que corta (mapa_json.pecas_parte). A grade por tamanho é do ENFESTO e
sai uma vez só, em grupos[] — o motor v1 repetia a grade do enfesto em todas
as partes e o formulário a somava uma vez por parte.
"""

from __future__ import annotations

import math
import uuid
from decimal import Decimal

from fastapi import HTTPException
from markupsafe import Markup, escape
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polylabel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models.encaixe import Encaixe
from models.ordem_corte import COMPRIMENTO_MAX_PADRAO_CM, ItemOrdemCorte, OrdemCorte, OrdemCorteTecido
from models.pedido import PedidoVenda
from models.produto_sku import ProdutoSKU
from models.tecido import CorTecido, LoteTecido
from services.ordem_corte_service import numero_fmt
from services.relatorios.dados_pedido import _empresa

_MODO = {"SEM_SOBRA": "Sem sobra", "MENOS_ENFESTOS": "Menos enfestos"}
_QUALIDADE = {"RAPIDO": "Rápido", "EQUILIBRADO": "Equilibrado", "MAXIMO": "Máximo"}
_STATUS = {
    "RASCUNHO": "Rascunho",
    "ENVIADA": "Enviada",
    "EM_CORTE": "Em corte",
    "CONCLUIDA": "Concluída",
    "CANCELADA": "Cancelada",
}

# Desenho da mesa (os dois formulários): DEITADO e visto do lado do
# cortador — ele fica de frente para a largura do tecido, no início da mesa.
# O encaixe é GIRADO 180° (x e y invertidos juntos, nunca um eixo só: isso
# espelharia as peças): largura na horizontal com a cota embaixo e "INÍCIO DA
# MESA" logo abaixo dela; comprimento na vertical com a cota à esquerda.
# Escala fixa: 150 cm de tecido ≈ 100 mm no papel; o desenho inteiro (com as
# cotas) vai até 110 × 90 mm e, se passar, encolhe mantendo a proporção.
# Textos em pt convertidos para mm (unidade do SVG).
_PT_MM = 0.3528
_DESENHO_ESCALA_MM_CM = 100.0 / 150.0
_DESENHO_LARGURA_MAX_MM = 110.0
_DESENHO_ALTURA_MAX_MM = 90.0
_DESENHO_MARGEM_ESQ_MM = 6.5  # cota do comprimento
_DESENHO_MARGEM_TOPO_MM = 1.0
_DESENHO_MARGEM_BAIXO_MM = 9.6  # cota da largura + "INÍCIO DA MESA"
_DESENHO_MARGEM_DIR_MM = 0.5
_DESENHO_FONTE_COTA_MM = 7 * _PT_MM
_DESENHO_FONTE_MAX_MM = 8 * _PT_MM
_DESENHO_FONTE_MIN_MM = 5 * _PT_MM

_TIPO_ENFESTO = ("MESMA_FACE", "FACE_A_FACE")
NOME_TIPO_ENFESTO = {"MESMA_FACE": "Enfesto simples", "FACE_A_FACE": "Enfesto duplo"}


def _dec(valor, casas: int = 3) -> Decimal:
    return Decimal(str(round(float(valor or 0), casas)))


def _txt(valor) -> str:
    return str(valor or "").strip()


# ── Grade cor × tamanho ───────────────────────────────────────────────────────


# Ordem usual dos tamanhos — só quando o item não tem SKU (sem tabela de grade).
_ORDEM_TAMANHOS = ("PP", "P", "M", "G", "GG", "XG", "XGG", "EG", "EGG", "G1", "G2", "G3", "G4")


def _grades(itens: list[ItemOrdemCorte]) -> list[dict]:
    """Uma grade por produto pai. Cores e tamanhos na ordem da tabela de
    grade (ItemTabelaGrade.ordem); sem SKU/ordem, tamanhos na ordem usual
    (_ORDEM_TAMANHOS) e cores na ordem do pedido."""
    produtos: dict[uuid.UUID, dict] = {}
    for pos, i in enumerate(itens):
        g = produtos.setdefault(
            i.produto_pai_id,
            {
                "codigo": _txt(i.produto_pai.codigo if i.produto_pai else ""),
                "descricao": _txt(i.produto_pai.descricao if i.produto_pai else ""),
                "cores": {},
                "tamanhos": {},
                "qtd": {},
            },
        )
        sku = i.sku
        cor = _txt(i.cor) or "—"
        tam = _txt(i.tamanho) or "—"
        ordem_cor = sku.linha_item.ordem if sku and sku.linha_item else 10_000 + pos
        if sku and sku.coluna_item:
            ordem_tam = sku.coluna_item.ordem
        elif tam.upper() in _ORDEM_TAMANHOS:
            ordem_tam = 5_000 + _ORDEM_TAMANHOS.index(tam.upper())
        else:
            ordem_tam = 10_000 + pos
        g["cores"].setdefault(cor, (ordem_cor, pos))
        g["tamanhos"].setdefault(tam, (ordem_tam, pos))
        g["qtd"][(cor, tam)] = g["qtd"].get((cor, tam), 0) + (i.quantidade or 0)

    saida = []
    for produto_id, g in produtos.items():
        cores = sorted(g["cores"], key=g["cores"].get)
        tamanhos = sorted(g["tamanhos"], key=g["tamanhos"].get)
        linhas = [
            {
                "cor": cor,
                "quantidades": [g["qtd"].get((cor, t), 0) for t in tamanhos],
                "total": sum(g["qtd"].get((cor, t), 0) for t in tamanhos),
            }
            for cor in cores
        ]
        saida.append(
            {
                "produto_id": str(produto_id),
                "produto_codigo": g["codigo"],
                "produto_descricao": g["descricao"],
                "tamanhos": tamanhos,
                "linhas": linhas,
                "totais_tamanho": [sum(g["qtd"].get((c, t), 0) for c in cores) for t in tamanhos],
                "total": sum(ln["total"] for ln in linhas),
            }
        )
    return saida


# ── Desenho da mesa ───────────────────────────────────────────────────────────


def _rotacionar(pts: list, graus: float) -> list[tuple[float, float]]:
    if not graus:
        return [(float(x), float(y)) for x, y in pts]
    rad = math.radians(graus)
    c, s = math.cos(rad), math.sin(rad)
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def _pontos_tela(pl: dict) -> list[tuple[float, float]] | None:
    """Polígono da peça em cm na tela, no referencial do motor: X = largura
    do tecido (pl.x + x), Y = comprimento da mesa (pl.y + y, 0 = início da
    mesa, em cima). Rotacionado na origem e normalizado pelo canto do
    bounding box, como no VisualizadorEncaixe. Dados inválidos → None."""
    try:
        pts = _rotacionar(pl["polygon"], float(pl.get("rotation") or 0))
        min_x = min(x for x, _ in pts)
        min_y = min(y for _, y in pts)
        ox, oy = float(pl.get("x") or 0), float(pl.get("y") or 0)
    except (TypeError, ValueError, KeyError):
        return None
    return [(ox + (x - min_x), oy + (y - min_y)) for x, y in pts]


def _cm(valor: float) -> str:
    """150.0 → "150 cm"; 149.5 → "149,5 cm"."""
    return f"{valor:.0f} cm" if abs(valor - round(valor)) < 0.05 else f"{valor:.1f} cm".replace(".", ",")


def _centro(pts: list[tuple[float, float]]) -> tuple[float, float]:
    """Centroide do polígono (fórmula do laço); área ~0 → centro do bounding box."""
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        f = x0 * y1 - x1 * y0
        a += f
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    if abs(a) < 1e-9:
        xs, ys = [x for x, _ in pts], [y for _, y in pts]
        return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return cx / (3 * a), cy / (3 * a)


def _trecho(poligono: Polygon, centro: Point, a: tuple[float, float], b: tuple[float, float]) -> tuple[float, Point]:
    """Trecho da reta a–b que fica DENTRO da peça e passa pelo centro: (o
    comprimento — espaço livre para o texto naquela direção —, o ponto do
    meio do trecho). Nada → (0, centro)."""
    corte = LineString([a, b]).intersection(poligono)
    partes = [g for g in getattr(corte, "geoms", [corte]) if g.length and g.distance(centro) < 1e-6]
    if not partes:
        return 0.0, centro
    trecho = max(partes, key=lambda g: g.length)
    return trecho.length, trecho.interpolate(0.5, normalized=True)


def _espaco(pts: list[tuple[float, float]]) -> tuple[Point, Point, float, float]:
    """Onde escrever o nome da peça: (meio do trecho livre na horizontal,
    meio do trecho livre na vertical, comprimento de cada trecho).

    Os trechos passam pelo ponto mais longe das bordas (polylabel), não pelo
    centroide: em peça com fenda funda (FRENTE da legging) o centroide cai na
    tira estreita e o nome atravessa o contorno. O texto é centrado no MEIO
    do trecho na direção em que corre, para não sair da peça. Geometria
    inválida → centroide e bounding box."""
    xs, ys = [x for x, _ in pts], [y for _, y in pts]
    try:
        poligono = Polygon(pts).buffer(0)
        if poligono.geom_type == "MultiPolygon":
            poligono = max(poligono.geoms, key=lambda g: g.area)
        centro = polylabel(poligono, tolerance=0.2)
        livre_h, meio_h = _trecho(poligono, centro, (min(xs) - 1, centro.y), (max(xs) + 1, centro.y))
        livre_v, meio_v = _trecho(poligono, centro, (centro.x, min(ys) - 1), (centro.x, max(ys) + 1))
    except Exception:  # noqa: BLE001 — desenho nunca derruba o relatório
        livre_h = livre_v = 0.0
    if livre_h <= 0 or livre_v <= 0:
        centro = Point(_centro(pts))
        return centro, centro, max(xs) - min(xs), max(ys) - min(ys)
    return meio_h, meio_v, livre_h, livre_v


def _rotulo(pts: list[tuple[float, float]], linhas: list[str]) -> str:
    """Texto no miolo da peça (pts em mm, ver _espaco). A fonte é a maior
    que cabe no espaço livre, entre _DESENHO_FONTE_MIN_MM e
    _DESENHO_FONTE_MAX_MM; o texto fica na horizontal e só gira para a
    vertical em peça estreita (em pé), quando assim cabe bem maior."""
    meio_h, meio_v, w, h = _espaco(pts)
    n = max(len(t) for t in linhas)

    def fonte(larg: float, alt: float) -> float:
        # Tahoma negrito: ~0,62 em por caractere; linha = 1,15 em.
        return min(larg * 0.85 / (n * 0.62), alt * 0.8 / (len(linhas) * 1.15))

    horizontal, vertical = fonte(w, h), fonte(h, w)
    girar = vertical > horizontal * 1.2
    fs = max(_DESENHO_FONTE_MIN_MM, min(_DESENHO_FONTE_MAX_MM, vertical if girar else horizontal))
    cx, cy = (meio_v.x, meio_v.y) if girar else (meio_h.x, meio_h.y)
    # Primeira linha sobe metade do bloco; +0,35 em centraliza a altura da letra.
    y0 = cy - (len(linhas) - 1) * fs * 1.15 / 2 + fs * 0.35
    tspans = "".join(
        f'<tspan x="{cx:.2f}" y="{y0 + i * fs * 1.15:.2f}">{escape(t)}</tspan>' for i, t in enumerate(linhas)
    )
    giro = f' transform="rotate(-90 {cx:.2f} {cy:.2f})"' if girar else ""
    return f'<text font-size="{fs:.2f}"{giro}>{tspans}</text>'


def _girar_180(pts: list[tuple[float, float]], largura: float, comprimento: float) -> list[tuple[float, float]]:
    """Giro de 180° dentro do tecido: x → largura − x E y → comprimento − y
    (os dois juntos — um eixo só espelharia a peça). O início da mesa (y = 0
    no motor) passa para a borda de baixo, do lado do cortador."""
    return [(largura - x, comprimento - y) for x, y in pts]


def desenho_svg(mapa: dict | None) -> Markup:
    """Desenho da mesa para o cortador (os dois formulários), em mm, DEITADO
    e girado 180° (ver _girar_180): largura do tecido na horizontal com a
    cota embaixo e "INÍCIO DA MESA" (cinza) logo abaixo dela; comprimento da
    mesa na vertical com a cota à esquerda. Escala fixa (150 cm ≈ 100 mm) até
    110 × 90 mm no total. Peças com "MOLDE TAMANHO" no centro (5 a 8 pt);
    metade espelhada tracejada com "(esp.)". Só traço preto. Sem dados → ""."""
    mapa = mapa or {}
    try:
        largura = float(mapa.get("largura_cm") or 0)
        comprimento = float(mapa.get("comprimento_cm") or 0)
    except (TypeError, ValueError):
        return Markup("")
    placements = [p for p in mapa.get("placements") or [] if len(p.get("polygon") or []) >= 3]
    if largura <= 0 or comprimento <= 0 or not placements:
        return Markup("")

    esq, topo, baixo = _DESENHO_MARGEM_ESQ_MM, _DESENHO_MARGEM_TOPO_MM, _DESENHO_MARGEM_BAIXO_MM
    escala = min(
        _DESENHO_ESCALA_MM_CM,
        (_DESENHO_LARGURA_MAX_MM - esq - _DESENHO_MARGEM_DIR_MM) / largura,
        (_DESENHO_ALTURA_MAX_MM - topo - baixo) / comprimento,
    )  # mm por cm
    w, h = largura * escala, comprimento * escala
    pecas, rotulos = [], []
    for pl in placements:
        pts = _pontos_tela(pl)
        if pts is None:
            continue
        pts = [(esq + x * escala, topo + y * escala) for x, y in _girar_180(pts, largura, comprimento)]
        pontos = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        espelhada = bool(pl.get("espelhada"))
        tracejado = ' stroke-dasharray="1 0.6"' if espelhada else ""
        pecas.append(f'<polygon points="{pontos}"{tracejado}/>')
        nome = " ".join(t for t in (_txt(pl.get("peca")), _txt(pl.get("tamanho"))) if t) or "PEÇA"
        rotulos.append(_rotulo(pts, [nome, "(esp.)"] if espelhada else [nome]))

    # Cotas: linha com traços nas pontas, texto por fora do tecido — largura
    # embaixo (e "INÍCIO DA MESA" logo abaixo dela), comprimento à esquerda.
    # Textos das cotas e "INÍCIO DA MESA" em 7 pt.
    fc = _DESENHO_FONTE_COTA_MM
    yc, xc = topo + h + 1.8, esq - 1.8
    y_largura = yc + 1.2 + fc
    cotas = (
        f'<g stroke-width="0.2">'
        f'<line x1="{esq:.2f}" y1="{yc:.2f}" x2="{esq + w:.2f}" y2="{yc:.2f}"/>'
        f'<line x1="{esq:.2f}" y1="{yc - 1.2:.2f}" x2="{esq:.2f}" y2="{yc + 1.2:.2f}"/>'
        f'<line x1="{esq + w:.2f}" y1="{yc - 1.2:.2f}" x2="{esq + w:.2f}" y2="{yc + 1.2:.2f}"/>'
        f'<line x1="{xc:.2f}" y1="{topo:.2f}" x2="{xc:.2f}" y2="{topo + h:.2f}"/>'
        f'<line x1="{xc - 1.2:.2f}" y1="{topo:.2f}" x2="{xc + 1.2:.2f}" y2="{topo:.2f}"/>'
        f'<line x1="{xc - 1.2:.2f}" y1="{topo + h:.2f}" x2="{xc + 1.2:.2f}" y2="{topo + h:.2f}"/>'
        f"</g>"
        f'<g fill="#000" stroke="none" font-size="{fc:.2f}" text-anchor="middle">'
        f'<text x="{esq + w / 2:.2f}" y="{y_largura:.2f}">{_cm(largura)}</text>'
        f'<text x="{xc - 1.4:.2f}" y="{topo + h / 2:.2f}" transform="rotate(-90 {xc - 1.4:.2f} {topo + h / 2:.2f})">'
        f"{round(comprimento)} cm</text>"
        f"</g>"
        f'<text x="{esq + w / 2:.2f}" y="{y_largura + 0.9 + fc:.2f}" fill="#777" stroke="none" font-size="{fc:.2f}" '
        f'font-weight="normal" text-anchor="middle">INÍCIO DA MESA</text>'
    )
    largura_svg, altura_svg = esq + w + _DESENHO_MARGEM_DIR_MM, topo + h + baixo
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura_svg:.1f}mm" height="{altura_svg:.1f}mm" '
        f'viewBox="0 0 {largura_svg:.2f} {altura_svg:.2f}" '
        f'font-family="Tahoma, Verdana, sans-serif" font-weight="bold">'
        f'<g fill="none" stroke="#000" stroke-linejoin="round">'
        f'<rect x="{esq}" y="{topo}" width="{w:.2f}" height="{h:.2f}" stroke-width="0.35"/>'
        f'<g stroke-width="0.2">{"".join(pecas)}</g>'
        f"{cotas}"
        f"</g>"
        f'<g fill="#000" text-anchor="middle">{"".join(rotulos)}</g>'
        f"</svg>"
    )
    return Markup(svg)


def tipo_enfesto(mapa: dict | None) -> str:
    """MESMA_FACE | FACE_A_FACE gravado pela geração; ausente/inválido →
    MESMA_FACE (encaixes de antes da decisão automática do enfesto)."""
    valor = _txt((mapa or {}).get("tipo_enfesto")).upper()
    return valor if valor in _TIPO_ENFESTO else "MESMA_FACE"


def enfesto_texto(tipo: str, camadas: int) -> str:
    """Campo ENFESTO do formulário: "Enfesto duplo · 6 camadas"."""
    camadas = max(1, int(camadas or 1))
    return f"{NOME_TIPO_ENFESTO.get(tipo, NOME_TIPO_ENFESTO['MESMA_FACE'])} · {camadas} camada{'s' if camadas != 1 else ''}"


# ── Enfestos ──────────────────────────────────────────────────────────────────


def numero_encaixe(numero: int | None) -> str:
    """ENC-001 — mesmo formato da tela da OC (fmtEnc)."""
    return f"ENC-{numero:03d}" if numero is not None else "ENC-—"


def _pecas_por_produto(pecas: list[dict]) -> list[dict]:
    """Agrupa as linhas do mapa por produto (grupo_nome), na ordem em que
    aparecem, para o tamanho não repetir o nome do produto."""
    grupos: dict[str, list[dict]] = {}
    for p in pecas:
        grupos.setdefault(_txt(p.get("grupo_nome")), []).append(
            {
                "tamanho": _txt(p.get("tamanho")),
                # conjuntos = peças inteiras daquele tamanho em UMA camada
                "por_camada": int(p.get("conjuntos") or 0),
                "total": int(p.get("pecas") or 0),
                "sobra": int(p.get("sobra") or 0),
            }
        )
    return [{"produto": produto, "tamanhos": tamanhos} for produto, tamanhos in grupos.items()]


def _moldes(mapa: dict, camadas: int) -> list[dict]:
    """Moldes que a MESA corta, agrupados por produto: [{produto, moldes[]
    {molde, tamanho, por_camada, total, espelhadas}}]. Vem de
    mapa_json.pecas_parte; encaixe antigo sem ela conta pelos placements."""
    linhas = mapa.get("pecas_parte")
    if not linhas:
        acc: dict[tuple, dict] = {}
        for pl in mapa.get("placements") or []:
            k = (pl.get("id"), _txt(pl.get("peca")), _txt(pl.get("tamanho")), _txt(pl.get("grupo_nome")))
            linha = acc.setdefault(
                k, {"peca": k[1], "tamanho": k[2], "grupo_nome": k[3], "por_camada": 0, "espelhadas": 0}
            )
            linha["por_camada"] += 1
            linha["espelhadas"] += int(bool(pl.get("espelhada")))
        linhas = list(acc.values())
    grupos: dict[str, list[dict]] = {}
    for p in linhas:
        por_camada = int(p.get("por_camada") or p.get("quantidade") or 0)
        grupos.setdefault(_txt(p.get("grupo_nome") or p.get("produto")), []).append(
            {
                "molde": _txt(p.get("peca") or p.get("molde")) or "Peça",
                "tamanho": _txt(p.get("tamanho")),
                "por_camada": por_camada,
                "total": por_camada * camadas,
                "espelhadas": int(p.get("espelhadas") or 0),
            }
        )
    return [{"produto": produto, "moldes": moldes} for produto, moldes in grupos.items()]


def _motor(mapa: dict) -> str:
    """ "Motor v2 · Automático (Máximo)" | "Motor v2 · Equilibrado" | "" (encaixe
    antigo, gerado sem motor_usado)."""
    if mapa.get("motor_usado") != "v2":
        return ""
    perfil = _QUALIDADE.get(mapa.get("qualidade_perfil") or mapa.get("qualidade"), "Equilibrado")
    if mapa.get("qualidade") == "AUTOMATICO":
        return f"Motor v2 · Automático ({perfil})"
    return f"Motor v2 · {perfil}"


def _parte(mapa: dict) -> tuple[int | None, int | None]:
    """(parte, total) do enfesto dividido — encaixes antigos só têm o texto
    "1/2" em "parte"; enfesto inteiro devolve (None, None)."""
    total = mapa.get("total_partes")
    if total:
        return (mapa.get("parte_numero"), int(total)) if int(total) > 1 else (None, None)
    n, _, total = _txt(mapa.get("parte")).partition("/")
    return (int(n), int(total)) if n.isdigit() and total.isdigit() else (None, None)


def _pecas_acima_do_limite(mapa: dict, limite_cm: int) -> list[str]:
    """Nota para cada peça mais comprida que a mesa (mesmo texto do aviso da
    geração). Comprimento = extensão da peça ao longo do enfesto na rotação
    em que foi encaixada (a mesma conta da miniatura)."""
    notas: dict[str, None] = {}
    for pl in mapa.get("placements") or []:
        try:
            pts = _rotacionar(pl["polygon"], float(pl.get("rotation") or 0))
        except (TypeError, ValueError, KeyError):
            continue
        comprimento = max(y for _, y in pts) - min(y for _, y in pts)
        if comprimento > limite_cm + 1e-3:
            nome = " ".join(t for t in (_txt(pl.get("peca")), _txt(pl.get("tamanho"))) if t) or "sem nome"
            notas.setdefault(f"Peça {nome} ({comprimento:.1f} cm) maior que o limite de {limite_cm} cm", None)
    return list(notas)


def _enfesto(e: Encaixe, limite_oc: int) -> dict:
    mapa = e.mapa_json or {}
    # Limite com que o encaixe foi gerado; encaixes de antes do limite
    # existir usam o da OC.
    limite = int(mapa.get("comprimento_max_cm") or limite_oc)
    parte, total_partes = _parte(mapa)
    camadas = int(e.num_camadas or 1)
    lote = e.lote
    cor = lote.cor if lote else None
    grupos = _pecas_por_produto(mapa.get("pecas_por_tamanho") or [])
    pecas = [t for g in grupos for t in g["tamanhos"]]
    moldes = _moldes(mapa, camadas)
    avisos = _pecas_acima_do_limite(mapa, limite)
    tecido = {
        "nome": _txt(mapa.get("tecido_nome")),
        "modelo": _txt(cor.modelo.nome if cor and cor.modelo else ""),
        "cor": _txt(cor.nome_cor if cor else ""),
        "lote": _txt(lote.codigo_lote if lote else ""),
    }
    if e.camadas_cor:
        # Enfesto multicor (plano por produto): todas as cores e lotes, na
        # ordem do enfesto. A ficha por produto (relPro001) é o Passo 4.
        tecido["cor"] = " + ".join(f"{_txt(c.cor)} {c.camadas}" for c in e.camadas_cor)
        tecido["lote"] = " + ".join(_txt(c.lote.codigo_lote) for c in e.camadas_cor if c.lote)
    tipo = tipo_enfesto(mapa)
    desenho = desenho_svg(mapa)
    return {
        "lote_id": str(e.lote_id) if e.lote_id else "",
        # Grupo de corte: o lote (OC por cor) ou lote + produto (OC por produto).
        "grupo_corte": _txt(mapa.get("grupo_corte")) or (str(e.lote_id) if e.lote_id else ""),
        "numero": e.numero,
        "numero_formatado": numero_encaixe(e.numero),
        "enfesto": mapa.get("enfesto"),
        "parte": _txt(mapa.get("parte")),
        "parte_numero": parte,
        "total_partes": total_partes,
        "comprimento_max_cm": limite,
        "avisos": avisos,
        "tecido": tecido,
        "largura_util_cm": _dec(mapa.get("largura_cm") or (cor.largura_util_cm if cor else 0), 1),
        "comprimento_m": _dec(e.comp_metros, 3),
        "camadas": camadas,
        "motor": _motor(mapa),
        "moldes": moldes,
        "moldes_por_camada": sum(m["por_camada"] for g in moldes for m in g["moldes"]),
        "moldes_total": sum(m["total"] for g in moldes for m in g["moldes"]),
        "tem_espelhadas": any(m["espelhadas"] for g in moldes for m in g["moldes"]),
        # Grade do ENFESTO como gravada NESTE encaixe (o v1 a repete em todas
        # as partes, o v2 só na parte 1) — o modelo usa grupos[].pecas_por_tamanho.
        "pecas_por_tamanho": grupos,
        "sobra_total": sum(p["sobra"] for p in pecas),
        "pecas_por_camada": sum(p["por_camada"] for p in pecas),
        "pecas_total": sum(p["total"] for p in pecas),
        # peso_kg do Encaixe é de UMA camada
        "peso_total_kg": _dec(float(e.peso_kg or 0) * camadas, 3),
        "aproveitamento": (_dec(100 - float(e.desperdicio_pct), 1) if e.desperdicio_pct is not None else None),
        "tipo_enfesto": tipo,
        "tipo_enfesto_nome": NOME_TIPO_ENFESTO[tipo],
        "enfesto_texto": enfesto_texto(tipo, camadas),
        "desenho_svg": desenho,
        # Nome antigo do desenho: continua existindo (o mesmo desenho novo)
        # para não quebrar variantes personalizadas do modelo.
        "miniatura_svg": desenho,
    }


def _nome_tecido(tecido: dict) -> str:
    """ "MAXXI PRETO" (modelo + cor); sem cadastro, o nome gravado no mapa."""
    return " ".join(t for t in (tecido["modelo"], tecido["cor"]) if t) or tecido["nome"]


def _grupos(enfestos: list[dict]) -> list[dict]:
    """Mesas agrupadas por enfesto (grupo de corte + número), na ordem dos encaixes.
    A grade por tamanho, a sobra e as peças do enfesto vêm da primeira mesa
    que as tem — uma vez por enfesto, nunca somadas por parte."""
    grupos: dict[tuple, dict] = {}
    for e in enfestos:
        chave = (e["grupo_corte"], e["enfesto"]) if e["enfesto"] is not None else ("", e["numero"])
        g = grupos.get(chave)
        if g is None:
            g = grupos[chave] = {
                "enfesto": e["enfesto"],
                "tecido": e["tecido"],
                "largura_util_cm": e["largura_util_cm"],
                "camadas": e["camadas"],
                "motor": e["motor"],
                "pecas_por_tamanho": [],
                "pecas_por_camada": 0,
                "pecas_total": 0,
                "sobra_total": 0,
                "mesas": [],
            }
        g["mesas"].append(e)
        if not g["pecas_por_tamanho"] and e["pecas_por_tamanho"]:
            g["pecas_por_tamanho"] = e["pecas_por_tamanho"]
            g["pecas_por_camada"] = e["pecas_por_camada"]
            g["pecas_total"] = e["pecas_total"]
            g["sobra_total"] = e["sobra_total"]
    for g in grupos.values():
        g["total_mesas"] = len(g["mesas"])
        g["comprimento_m"] = _dec(sum(m["comprimento_m"] for m in g["mesas"]), 3)
        g["peso_total_kg"] = _dec(sum(m["peso_total_kg"] for m in g["mesas"]), 3)
    return list(grupos.values())


def _mesa(e: Encaixe, enf: dict, numero: int, total: int) -> dict:
    """Uma mesa do formulário do cortador: o que estender (tecido, medidas,
    enfesto) e o que cortar. pecas = vezes que o molde aparece no desenho
    (espelhadas contam); o total cortado é pecas × camadas."""
    mapa = e.mapa_json or {}
    cortar = [
        {"molde": m["molde"], "tamanho": m["tamanho"], "pecas": m["por_camada"], "espelhadas": m["espelhadas"]}
        for g in enf["moldes"]
        for m in g["moldes"]
    ]
    comprimento = float(mapa.get("comprimento_cm") or 0) or float(e.comp_metros or 0) * 100
    # Hoje um enfesto tem uma cor só; a lista já comporta várias.
    cores = [{"cor": enf["tecido"]["cor"] or "—", "camadas": enf["camadas"]}]
    camadas = sum(c["camadas"] for c in cores)
    return {
        "numero_mesa": numero,
        "total_mesas": total,
        "tecido": enf["tecido"]["modelo"] or enf["tecido"]["nome"],
        "tecido_cor": _nome_tecido(enf["tecido"]),
        "lote": enf["tecido"]["lote"],
        "comprimento_cm": round(comprimento),
        "largura_cm": enf["largura_util_cm"],
        "largura_texto": _cm(float(enf["largura_util_cm"] or 0)),
        "cores": cores,
        "camadas": camadas,
        "cortar": cortar,
        "avisos": enf["avisos"],
        "tipo_enfesto": enf["tipo_enfesto"],
        "tipo_enfesto_nome": enf["tipo_enfesto_nome"],
        "enfesto_texto": enfesto_texto(enf["tipo_enfesto"], camadas),
        "desenho_svg": enf["desenho_svg"],
    }


# ── Ficha por produto (OC organizada por PRODUTO) ─────────────────────────────


def _camadas_texto(e: Encaixe) -> str:
    """ "PRETO 7 · MARROM 7" — as cores do enfesto, de baixo para cima."""
    if e.camadas_cor:
        return " · ".join(f"{_txt(c.cor)} {c.camadas}" for c in e.camadas_cor)
    cor = e.lote.cor.nome_cor if e.lote and e.lote.cor else ""
    return f"{_txt(cor)} {e.num_camadas or 1}".strip()


def _produtos(oc: OrdemCorte, encaixes: list[Encaixe], mesas: list[dict], grades: list[dict]) -> list[dict]:
    """Seções da ficha por produto: produto → tecido → grade do pedido e mesas.

    As mesas seguem a ordem de corte (a dos encaixes) e mantêm o número da
    OC. O tecido de cada cor do pedido é o do lote escolhido para ela
    (OrdemCorteTecido) — é assim que a grade se divide entre os tecidos
    quando um produto usa mais de um (ex.: MAXXI e CANELADO)."""
    if not encaixes or any(not (e.mapa_json or {}).get("produto_id") for e in encaixes):
        return []
    modelo_da_cor: dict[tuple[str, str], str] = {}
    for t in oc.tecidos:
        if t.lote and t.lote.cor and t.lote.cor.modelo:
            modelo_da_cor[(str(t.produto_pai_id), _txt(t.cor).casefold())] = t.lote.cor.modelo.nome
    grade_por_produto = {g["produto_id"]: g for g in grades}

    # O desenho de um risco dividido em mesas: os tamanhos saem da 1ª mesa de
    # cada enfesto (pecas_por_tamanho só vai nela).
    tamanhos_risco: dict[tuple, str] = {}
    for e in encaixes:
        mapa = e.mapa_json or {}
        linhas = mapa.get("pecas_por_tamanho") or []
        if linhas:
            chave = (mapa.get("grupo_corte"), mapa.get("risco"))
            tamanhos_risco.setdefault(chave, " ".join(f"{ln['tamanho']}{ln['conjuntos']}" for ln in linhas))

    secoes: dict[str, dict] = {}
    for e, m in zip(encaixes, mesas):
        mapa = e.mapa_json or {}
        produto_id = str(mapa["produto_id"])
        modelo = (
            e.lote.cor.modelo.nome if e.lote and e.lote.cor and e.lote.cor.modelo else _txt(mapa.get("tecido_nome"))
        )
        prod = secoes.setdefault(
            produto_id,
            {"produto": _txt(mapa.get("produto_nome")), "codigo": "", "tecidos": {}},
        )
        g = grade_por_produto.get(produto_id)
        if g:
            prod["produto"], prod["codigo"] = g["produto_descricao"] or prod["produto"], g["produto_codigo"]
        sec = prod["tecidos"].setdefault(modelo, {"tecido": modelo, "grade": None, "mesas": [], "_blocos": {}})
        partes = int(mapa.get("total_partes") or 1)
        # Enfestos do MESMO risco (mesma parte) têm o mesmo desenho: um bloco
        # só, com as camadas de cada mesa — o desenho não se repete na folha.
        chave = (mapa.get("grupo_corte"), mapa.get("risco"), mapa.get("parte_numero"))
        bloco = sec["_blocos"].get(chave)
        if bloco is None:
            bloco = sec["_blocos"][chave] = {
                **m,
                "tamanhos_texto": tamanhos_risco.get((mapa.get("grupo_corte"), mapa.get("risco")), ""),
                "parte_texto": f"parte {mapa.get('parte_numero')} de {partes}" if partes > 1 else "",
                "largura_texto": _cm(float(mapa.get("largura_cm") or m["largura_cm"] or 0)),
                "enfestos": [],
            }
            sec["mesas"].append(bloco)
        bloco["enfestos"].append({"numero_mesa": m["numero_mesa"], "camadas_texto": _camadas_texto(e)})
        bloco["camadas_texto"] = bloco["enfestos"][0]["camadas_texto"]

    saida = []
    for produto_id, prod in secoes.items():
        g = grade_por_produto.get(produto_id)
        tecidos = []
        for modelo, sec in prod["tecidos"].items():
            sec.pop("_blocos", None)
            if g:
                linhas = [
                    ln for ln in g["linhas"] if modelo_da_cor.get((produto_id, ln["cor"].casefold()), modelo) == modelo
                ]
                sec["grade"] = {"tamanhos": g["tamanhos"], "linhas": linhas}
            tecidos.append(sec)
        saida.append({"produto": prod["produto"], "codigo": prod["codigo"], "tecidos": tecidos})
    return saida


# ── Contexto ──────────────────────────────────────────────────────────────────


def _carregar_oc(db: Session, oc_id: uuid.UUID) -> OrdemCorte | None:
    return (
        db.execute(
            select(OrdemCorte)
            .where(OrdemCorte.id == oc_id)
            .options(
                selectinload(OrdemCorte.pedido).selectinload(PedidoVenda.vendedor),
                selectinload(OrdemCorte.itens).selectinload(ItemOrdemCorte.produto_pai),
                selectinload(OrdemCorte.itens).selectinload(ItemOrdemCorte.sku).selectinload(ProdutoSKU.linha_item),
                selectinload(OrdemCorte.itens).selectinload(ItemOrdemCorte.sku).selectinload(ProdutoSKU.coluna_item),
                selectinload(OrdemCorte.encaixes)
                .selectinload(Encaixe.lote)
                .selectinload(LoteTecido.cor)
                .selectinload(CorTecido.modelo),
                selectinload(OrdemCorte.encaixes).selectinload(Encaixe.camadas_cor),
                selectinload(OrdemCorte.tecidos)
                .selectinload(OrdemCorteTecido.lote)
                .selectinload(LoteTecido.cor)
                .selectinload(CorTecido.modelo),
            )
        )
        .scalars()
        .first()
    )


def _carregar_rapido(db: Session, pedido_id: uuid.UUID) -> tuple[PedidoVenda | None, list[Encaixe]]:
    """Pedido e encaixes do Encaixe Rápido: os do pedido que não são de OC."""
    pedido = (
        db.execute(
            select(PedidoVenda)
            .where(PedidoVenda.id == pedido_id)
            .options(selectinload(PedidoVenda.vendedor), selectinload(PedidoVenda.itens))
        )
        .scalars()
        .first()
    )
    if pedido is None:
        return None, []
    encaixes = (
        db.execute(
            select(Encaixe)
            .where(
                Encaixe.pedido_id == pedido_id,
                Encaixe.ordem_corte_id.is_(None),
                Encaixe.status != "deletado",
            )
            .options(
                selectinload(Encaixe.lote).selectinload(LoteTecido.cor).selectinload(CorTecido.modelo),
                selectinload(Encaixe.camadas_cor),
            )
        )
        .scalars()
        .all()
    )
    return pedido, list(encaixes)


def _dados_pedido(pedido: PedidoVenda | None) -> dict:
    return {
        "numero": _txt(pedido.numero if pedido else ""),
        "emissao": pedido.data_emissao if pedido else None,
        "cliente": _txt(pedido.cliente_razao_social if pedido else ""),
        "cliente_codigo": _txt(pedido.cliente_codigo if pedido else ""),
        "vendedor": _txt((pedido.vendedor.nome if pedido.vendedor else pedido.representante) if pedido else ""),
    }


def _contexto(
    db: Session,
    *,
    oc: dict,
    pedido: PedidoVenda | None,
    encaixes: list[Encaixe],
    limite_cm: int,
    grades: list[dict],
    pecas_pedido: int,
    produtos,
) -> dict:
    """Contexto comum à OC e ao Encaixe Rápido. `produtos(encaixes, mesas)`
    monta a ficha por produto (ou devolve [])."""
    encaixes = sorted(encaixes, key=lambda e: (e.numero or 0, e.criado_em))
    enfestos = [_enfesto(e, limite_cm) for e in encaixes]
    # Um enfesto dividido em várias mesas (parte 1/2 e 2/2) conta uma vez:
    # peças cortadas e sobra saem da grade de cada ENFESTO, não de cada parte.
    grupos = _grupos(enfestos)
    # Mesas na ordem de corte (a dos encaixes), numeradas 1..N.
    mesas = [_mesa(e, enf, i, len(encaixes)) for i, (e, enf) in enumerate(zip(encaixes, enfestos), 1)]

    return {
        "empresa": _empresa(db),
        "oc": oc,
        "pedido": _dados_pedido(pedido),
        "grades": grades,
        "enfestos": enfestos,
        "grupos": grupos,
        "mesas": mesas,
        "produtos": produtos(encaixes, mesas),
        "totais": {
            "pecas": pecas_pedido,
            "pecas_cortadas": sum(g["pecas_total"] for g in grupos),
            "sobra": sum(g["sobra_total"] for g in grupos),
            "enfestos": len(grupos),
            "mesas": len(enfestos),
            "metros": _dec(sum(float(e.comp_metros or 0) * (e.num_camadas or 1) for e in encaixes), 3),
            "peso_total_kg": _dec(sum(float(e.peso_kg or 0) * (e.num_camadas or 1) for e in encaixes), 3),
        },
    }


def montar(db: Session, id_registro: str) -> dict:
    """Contexto do relPro001. `id_registro` é o UUID de uma Ordem de Corte ou,
    no Encaixe Rápido (sem OC), o UUID do pedido do encaixe."""
    try:
        registro_id = uuid.UUID(str(id_registro))
    except ValueError:
        raise HTTPException(status_code=422, detail="id da Ordem de Corte inválido.")

    oc = _carregar_oc(db, registro_id)
    if oc is not None:
        grades = _grades(list(oc.itens))
        return _contexto(
            db,
            oc={
                "numero": numero_fmt(oc.numero),
                "data": oc.criado_em.date() if oc.criado_em else None,
                "status": _STATUS.get(oc.status, oc.status),
                "modo_camadas": _MODO.get(oc.modo_camadas, oc.modo_camadas),
                "comprimento_max_cm": oc.comprimento_max_cm,
                "observacoes": _txt(oc.observacoes),
                "organizar_por": oc.organizar_por,
            },
            pedido=oc.pedido,
            encaixes=[e for e in oc.encaixes if e.status != "deletado"],
            limite_cm=oc.comprimento_max_cm,
            grades=grades,
            pecas_pedido=sum(i.quantidade or 0 for i in oc.itens),
            produtos=lambda encs, mesas: _produtos(oc, encs, mesas, grades) if oc.organizar_por == "PRODUTO" else [],
        )

    pedido, encaixes = _carregar_rapido(db, registro_id)
    if not encaixes:
        raise HTTPException(status_code=404, detail="Ordem de Corte ou Encaixe Rápido não encontrado")
    # Encaixe Rápido: sem OC — a ficha sai pela lista de mesas, com o limite
    # de mesa com que os encaixes foram gerados.
    primeiro = min(encaixes, key=lambda e: e.criado_em)
    limite = int((primeiro.mapa_json or {}).get("comprimento_max_cm") or COMPRIMENTO_MAX_PADRAO_CM)
    return _contexto(
        db,
        oc={
            "numero": "Encaixe Rápido",
            "data": primeiro.criado_em.date() if primeiro.criado_em else None,
            "status": "sem OC",
            "modo_camadas": "",
            "comprimento_max_cm": limite,
            "observacoes": "",
            "organizar_por": "COR",
        },
        pedido=pedido,
        encaixes=encaixes,
        limite_cm=limite,
        grades=[],
        pecas_pedido=sum(i.quantidade_total for i in pedido.itens) if pedido else 0,
        produtos=lambda encs, mesas: [],
    )
