"""Fonte de dados do relPro001 (Formulário de corte da Ordem de Corte).

Mesmo contrato do relVen001 (dados_pedido): só tipos simples (dict/list/
str/Decimal/date) — o modelo roda em sandbox. A única exceção é
enfestos[].miniatura_svg, gerado aqui a partir do mapa_json e marcado como
seguro (Markup): o modelo não escreve JavaScript nem SVG.

Chaves: empresa, oc, pedido, grades, enfestos, totais (a engine acrescenta
"impressao").
"""

from __future__ import annotations

import math
import uuid
from decimal import Decimal

from fastapi import HTTPException
from markupsafe import Markup
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models.encaixe import Encaixe
from models.ordem_corte import ItemOrdemCorte, OrdemCorte
from models.pedido import PedidoVenda
from models.produto_sku import ProdutoSKU
from models.tecido import CorTecido, LoteTecido
from services.ordem_corte_service import numero_fmt
from services.relatorios.dados_pedido import _empresa

_MODO = {"SEM_SOBRA": "Sem sobra", "MENOS_ENFESTOS": "Menos enfestos"}
_STATUS = {
    "RASCUNHO": "Rascunho",
    "ENVIADA": "Enviada",
    "EM_CORTE": "Em corte",
    "CONCLUIDA": "Concluída",
    "CANCELADA": "Cancelada",
}

# Miniatura: comprimento do enfesto na horizontal (igual ao visualizador),
# até 180 mm de largura e 90 mm de altura.
_MINI_LARGURA_MM = 180.0
_MINI_ALTURA_MAX_MM = 90.0


def _dec(valor, casas: int = 3) -> Decimal:
    return Decimal(str(round(float(valor or 0), casas)))


def _txt(valor) -> str:
    return str(valor or "").strip()


# ── Grade cor × tamanho ───────────────────────────────────────────────────────


def _grades(itens: list[ItemOrdemCorte]) -> list[dict]:
    """Uma grade por produto pai. Cores e tamanhos na ordem da tabela de
    grade (ItemTabelaGrade.ordem); sem SKU/ordem, na ordem do pedido."""
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
        ordem_tam = sku.coluna_item.ordem if sku and sku.coluna_item else 10_000 + pos
        g["cores"].setdefault(cor, (ordem_cor, pos))
        g["tamanhos"].setdefault(tam, (ordem_tam, pos))
        g["qtd"][(cor, tam)] = g["qtd"].get((cor, tam), 0) + (i.quantidade or 0)

    saida = []
    for g in produtos.values():
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
                "produto_codigo": g["codigo"],
                "produto_descricao": g["descricao"],
                "tamanhos": tamanhos,
                "linhas": linhas,
                "totais_tamanho": [sum(g["qtd"].get((c, t), 0) for c in cores) for t in tamanhos],
                "total": sum(ln["total"] for ln in linhas),
            }
        )
    return saida


# ── Miniatura SVG ─────────────────────────────────────────────────────────────


def _rotacionar(pts: list, graus: float) -> list[tuple[float, float]]:
    if not graus:
        return [(float(x), float(y)) for x, y in pts]
    rad = math.radians(graus)
    c, s = math.cos(rad), math.sin(rad)
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def miniatura_svg(mapa: dict | None) -> Markup:
    """Contorno do tecido + peças (só traço preto) em escala. Mesma
    geometria do VisualizadorEncaixe: o motor devolve pl.x ao longo da
    LARGURA e pl.y ao longo do COMPRIMENTO; o polígono é rotacionado na
    origem e normalizado pelo canto do bounding box. Sem dados → ""."""
    mapa = mapa or {}
    try:
        largura = float(mapa.get("largura_cm") or 0)
        comprimento = float(mapa.get("comprimento_cm") or 0)
    except (TypeError, ValueError):
        return Markup("")
    placements = [p for p in mapa.get("placements") or [] if len(p.get("polygon") or []) >= 3]
    if largura <= 0 or comprimento <= 0 or not placements:
        return Markup("")

    escala = min(_MINI_LARGURA_MM / comprimento, _MINI_ALTURA_MAX_MM / largura)  # mm por cm
    w_mm, h_mm = comprimento * escala, largura * escala
    poligonos = []
    for pl in placements:
        try:
            pts = _rotacionar(pl["polygon"], float(pl.get("rotation") or 0))
            min_x = min(x for x, _ in pts)
            min_y = min(y for _, y in pts)
            ox, oy = float(pl.get("y") or 0), float(pl.get("x") or 0)
        except (TypeError, ValueError, KeyError):
            continue
        # Tela: X = comprimento (pl.y + y), Y = largura (pl.x + x).
        pontos = " ".join(f"{ox + (y - min_y):.1f},{oy + (x - min_x):.1f}" for x, y in pts)
        poligonos.append(f'<polygon points="{pontos}"/>')

    # Traço em unidades do viewBox (cm) para sair com espessura fixa em mm.
    traco_tecido, traco_peca = 0.3 / escala, 0.15 / escala
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm:.1f}mm" height="{h_mm:.1f}mm" '
        f'viewBox="0 0 {comprimento:.1f} {largura:.1f}" preserveAspectRatio="xMinYMin meet">'
        f'<g fill="none" stroke="#000" stroke-linejoin="round">'
        f'<rect x="0" y="0" width="{comprimento:.1f}" height="{largura:.1f}" stroke-width="{traco_tecido:.3f}"/>'
        f'<g stroke-width="{traco_peca:.3f}">{"".join(poligonos)}</g>'
        f"</g></svg>"
    )
    return Markup(svg)


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
    return {
        "numero": e.numero,
        "numero_formatado": numero_encaixe(e.numero),
        "enfesto": mapa.get("enfesto"),
        "parte": _txt(mapa.get("parte")),
        "parte_numero": parte,
        "total_partes": total_partes,
        "comprimento_max_cm": limite,
        "avisos": _pecas_acima_do_limite(mapa, limite),
        "tecido": {
            "nome": _txt(mapa.get("tecido_nome")),
            "modelo": _txt(cor.modelo.nome if cor and cor.modelo else ""),
            "cor": _txt(cor.nome_cor if cor else ""),
            "lote": _txt(lote.codigo_lote if lote else ""),
        },
        "largura_util_cm": _dec(mapa.get("largura_cm") or (cor.largura_util_cm if cor else 0), 1),
        "comprimento_m": _dec(e.comp_metros, 3),
        "camadas": camadas,
        "pecas_por_tamanho": grupos,
        "sobra_total": sum(p["sobra"] for p in pecas),
        "pecas_por_camada": sum(p["por_camada"] for p in pecas),
        "pecas_total": sum(p["total"] for p in pecas),
        # peso_kg do Encaixe é de UMA camada
        "peso_total_kg": _dec(float(e.peso_kg or 0) * camadas, 3),
        "aproveitamento": (_dec(100 - float(e.desperdicio_pct), 1) if e.desperdicio_pct is not None else None),
        "miniatura_svg": miniatura_svg(mapa),
    }


# ── Contexto ──────────────────────────────────────────────────────────────────


def montar(db: Session, id_registro: str) -> dict:
    """Contexto do relPro001 para a Ordem de Corte `id_registro` (UUID)."""
    try:
        oc_id = uuid.UUID(str(id_registro))
    except ValueError:
        raise HTTPException(status_code=422, detail="id da Ordem de Corte inválido.")
    oc = (
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
            )
        )
        .scalars()
        .first()
    )
    if oc is None:
        raise HTTPException(status_code=404, detail="Ordem de Corte não encontrada")

    pedido = oc.pedido
    encaixes = sorted((e for e in oc.encaixes if e.status != "deletado"), key=lambda e: (e.numero or 0, e.criado_em))
    enfestos = [_enfesto(e, oc.comprimento_max_cm) for e in encaixes]
    # Um enfesto dividido em dois encaixes (parte 1/2 e 2/2) conta uma vez.
    distintos = {(str(e.lote_id), (e.mapa_json or {}).get("enfesto") or str(e.id)) for e in encaixes}

    return {
        "empresa": _empresa(db),
        "oc": {
            "numero": numero_fmt(oc.numero),
            "data": oc.criado_em.date() if oc.criado_em else None,
            "status": _STATUS.get(oc.status, oc.status),
            "modo_camadas": _MODO.get(oc.modo_camadas, oc.modo_camadas),
            "comprimento_max_cm": oc.comprimento_max_cm,
            "observacoes": _txt(oc.observacoes),
        },
        "pedido": {
            "numero": _txt(pedido.numero if pedido else ""),
            "emissao": pedido.data_emissao if pedido else None,
            "cliente": _txt(pedido.cliente_razao_social if pedido else ""),
            "cliente_codigo": _txt(pedido.cliente_codigo if pedido else ""),
            "vendedor": _txt((pedido.vendedor.nome if pedido.vendedor else pedido.representante) if pedido else ""),
        },
        "grades": _grades(list(oc.itens)),
        "enfestos": enfestos,
        "totais": {
            "pecas": sum(i.quantidade or 0 for i in oc.itens),
            "enfestos": len(distintos),
            "metros": _dec(sum(float(e.comp_metros or 0) * (e.num_camadas or 1) for e in encaixes), 3),
            "peso_total_kg": _dec(sum(float(e.peso_kg or 0) * (e.num_camadas or 1) for e in encaixes), 3),
        },
    }
