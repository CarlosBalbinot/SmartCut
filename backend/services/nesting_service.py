"""nesting_service.py — Lógica de negócio para geração automática de encaixes.

Fluxo principal (gerar_encaixe):
  1. Carrega o pedido com todas as peças e tecidos vinculados.
  2. Agrupa PedidoPecas por lote (nova hierarquia) ou tecido legado.
  3. Para cada lote/tecido:
       a. Calcula num_camadas = min(modelo.max_camadas, max_qty_do_grupo).
       b. Monta a lista de moldes/polígonos para o worker (qty corrigida por
          camadas e pelo multiplicador de tipo_corte).
       c. Chama nesting_bridge.executar() → placements + comprimento usado.
       d. Se o comprimento excede MAX_ENFESTO_CM, divide as peças em lotes e
          cria um Encaixe por lote.
       e. Calcula comp_metros, peso_kg, custo_total e desperdicio_pct com
          aplicação do encolhimento.
       f. Salva um ou mais registros Encaixe no banco.
  4. Retorna lista de dicts resumindo os encaixes criados.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session, selectinload

from models.encaixe import Encaixe
from models.molde import Molde
from models.pedido import PedidoVenda as Pedido

# Stubs — PedidoPeca e PedidoTecido removidos na reestruturação
class PedidoPeca:
    pass

class PedidoTecido:
    pass
from models.tecido import CorTecido, LoteTecido, ModeloTecido
from nesting.nesting_bridge import build_polygon, executar
from services.gramatura_service import aplicar_encolhimento, calcular_custo, metros_para_peso

# Comprimento máximo (cm) de um único enfesto antes de criar um segundo lote.
# 2 000 cm = 20 m (tamanho típico de mesa de corte).
MAX_ENFESTO_CM: float = 2000.0

# Multiplicador de corte por tipo_corte (mesmo mapeamento usado em pedido_service)
_MULT: dict[str, int] = {"simples": 1, "par": 2, "par_sem_espelho": 2}


# ── DTO normalizado ──────────────────────────────────────────────────────────

@dataclass
class TecidoNesting:
    """Dados normalizados para nesting, independente de nova hierarquia ou legado."""
    nome: str
    largura_util_cm: float
    gramatura_g_m2: float
    valor_por_kg: float
    encolhimento_pct: float
    max_camadas: int
    lote_id: uuid.UUID | None       # nova hierarquia
    tecido_id: uuid.UUID | None     # legado

    @classmethod
    def de_lote(cls, lote: LoteTecido) -> "TecidoNesting":
        cor: CorTecido = lote.cor
        modelo: ModeloTecido = cor.modelo
        return cls(
            nome=f"{modelo.nome} — {cor.nome_cor}",
            largura_util_cm=float(cor.largura_util_cm),
            gramatura_g_m2=float(cor.gramatura_g_m2),
            valor_por_kg=float(lote.valor_kg),
            encolhimento_pct=float(cor.encolhimento_pct),
            max_camadas=int(modelo.max_camadas),
            lote_id=lote.id,
            tecido_id=None,
        )

    @classmethod
    def de_tecido_legado(cls, tecido: object) -> "TecidoNesting":
        return cls(
            nome=tecido.nome,  # type: ignore[attr-defined]
            largura_util_cm=float(tecido.largura_util_cm),  # type: ignore[attr-defined]
            gramatura_g_m2=float(tecido.gramatura_g_m2),  # type: ignore[attr-defined]
            valor_por_kg=float(tecido.valor_por_kg),  # type: ignore[attr-defined]
            encolhimento_pct=float(tecido.encolhimento_pct),  # type: ignore[attr-defined]
            max_camadas=int(tecido.max_camadas),  # type: ignore[attr-defined]
            lote_id=None,
            tecido_id=tecido.id,  # type: ignore[attr-defined]
        )


# ── Rotações permitidas por sentido do fio ───────────────────────────────────

def _rotacoes(sentido_fio: str | None) -> list[int]:
    """Converte sentido_fio em lista de rotações (graus) permitidas."""
    if sentido_fio == "vertical":
        return [0, 180]
    if sentido_fio == "horizontal":
        return [90, 270]
    if sentido_fio == "45graus":
        return [45, 135, 225, 315]
    return [0, 90, 180, 270]  # sem restrição


# ── Extração de polígono do molde ────────────────────────────────────────────

def _poligono(molde: Molde) -> list[list[float]]:
    return build_polygon(molde.geometria_json, molde.area_cm2)


def _rotate_polygon(pts: list[list[float]], angle_deg: int) -> list[list[float]]:
    """Rotaciona os pontos em torno do centróide do bounding box."""
    if not angle_deg:
        return pts
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    import math as _math
    rad = angle_deg * _math.pi / 180
    cos_a = _math.cos(rad)
    sin_a = _math.sin(rad)
    return [
        [cx + (x - cx) * cos_a - (y - cy) * sin_a,
         cy + (x - cx) * sin_a + (y - cy) * cos_a]
        for x, y in pts
    ]


def _poligono_rotacionado(molde: Molde) -> list[list[float]]:
    """Extrai o polígono e aplica rotacao_base antes de passar ao nesting."""
    pts = _poligono(molde)
    return _rotate_polygon(pts, molde.rotacao_base or 0)


# ── Agrupamento por lote (nova hierarquia) ou tecido legado ──────────────────

def _agrupar_por_lote_ou_tecido(
    pedido: Pedido,
) -> dict[str, tuple[TecidoNesting, list[PedidoPeca]]]:
    """Retorna {chave: (TecidoNesting, [pp, ...])}.

    Prioridade:
      1. Nova hierarquia: pp.cor_id → busca o lote do pedido cuja cor corresponde.
      2. Legado: pp.tecido ou o primeiro tecido do pedido.

    Peças sem nenhum tecido associado são ignoradas.
    """
    # Mapa cor_id → LoteTecido vindo de pedido_tecidos
    cor_to_lote: dict[uuid.UUID, LoteTecido] = {}
    for pt in pedido.pedido_tecidos:
        if pt.lote and pt.lote.cor:
            cor_id = pt.lote.cor.id
            if cor_id not in cor_to_lote:
                cor_to_lote[cor_id] = pt.lote

    # Tecido legado padrão (fallback)
    default_tecido = (
        pedido.pedido_tecidos[0].tecido
        if pedido.pedido_tecidos and pedido.pedido_tecidos[0].tecido
        else None
    )

    grupos: dict[str, tuple[TecidoNesting, list[PedidoPeca]]] = {}

    for pp in pedido.pecas:
        tn: TecidoNesting | None = None

        # 1. Nova hierarquia: cor_id presente na peça
        if pp.cor_id and pp.cor_id in cor_to_lote:
            lote = cor_to_lote[pp.cor_id]
            key = f"lote:{lote.id}"
            if key not in grupos:
                grupos[key] = (TecidoNesting.de_lote(lote), [])
            grupos[key][1].append(pp)
            continue

        # 2. Legado: tecido direto na peça ou fallback do pedido
        tecido = pp.tecido or default_tecido
        if tecido is None:
            continue
        key = f"tec:{tecido.id}"
        if key not in grupos:
            grupos[key] = (TecidoNesting.de_tecido_legado(tecido), [])
        grupos[key][1].append(pp)

    return grupos


# ── Geração de encaixes para um tecido ──────────────────────────────────────

def _gerar_para_tecido(
    db: Session,
    pedido: Pedido,
    tecido: TecidoNesting,
    pecas: list[PedidoPeca],
) -> list[dict]:
    """Roda nesting para um grupo tecido e salva um ou mais Encaixes."""

    max_qty = max(pp.quantidade for pp in pecas) if pecas else 1
    num_camadas = max(1, min(tecido.max_camadas, max_qty))

    parts: list[dict] = []
    for pp in pecas:
        m = pp.molde
        mult = _MULT.get(m.tipo_corte or "simples", 1)
        qty_plano = math.ceil(pp.quantidade * mult / num_camadas)
        if qty_plano <= 0:
            continue
        parts.append({
            "id": str(m.id),
            "polygon": _poligono_rotacionado(m),
            "quantity": qty_plano,
            "rotations": _rotacoes(m.sentido_fio),
        })

    if not parts:
        return []

    largura = tecido.largura_util_cm

    result = executar(
        bin_width_cm=largura,
        bin_height_cm=MAX_ENFESTO_CM,
        parts=parts,
    )

    encaixes_criados: list[dict] = []

    if result["width_used"] > MAX_ENFESTO_CM:
        encaixes_criados.extend(
            _dividir_em_lotes(db, pedido, tecido, parts, largura, num_camadas, pecas=pecas)
        )
    else:
        enc = _salvar_encaixe(
            db, pedido, tecido, result, num_camadas, largura, parts, pecas=pecas
        )
        encaixes_criados.append(enc)

    return encaixes_criados


def _dividir_em_lotes(
    db: Session,
    pedido: Pedido,
    tecido: TecidoNesting,
    parts: list[dict],
    largura: float,
    num_camadas: int,
    pecas: list | None = None,
) -> list[dict]:
    """Divide as partes em dois lotes e cria um Encaixe para cada um."""
    mid = max(1, len(parts) // 2)
    encaixes: list[dict] = []

    for lote in (parts[:mid], parts[mid:]):
        if not lote:
            continue
        result = executar(
            bin_width_cm=largura,
            bin_height_cm=MAX_ENFESTO_CM,
            parts=lote,
        )
        enc = _salvar_encaixe(
            db, pedido, tecido, result, num_camadas, largura, lote, pecas=pecas
        )
        encaixes.append(enc)

    return encaixes


def _salvar_encaixe(
    db: Session,
    pedido: Pedido,
    tecido: TecidoNesting,
    result: dict,
    num_camadas: int,
    largura_cm: float,
    parts: list[dict],
    pecas: list | None = None,
) -> dict:
    """Calcula métricas, salva Encaixe no banco e retorna dict resumo."""

    width_used_cm: float = result["width_used"]
    efficiency: float = result["efficiency"]

    comp_minimo_m = width_used_cm / 100.0
    comp_metros = aplicar_encolhimento(comp_minimo_m, tecido.encolhimento_pct)
    peso_kg = metros_para_peso(comp_metros, tecido.gramatura_g_m2, largura_cm)
    custo_total = calcular_custo(peso_kg, tecido.valor_por_kg)

    bin_area_cm2 = largura_cm * width_used_cm
    area_pecas_cm2 = bin_area_cm2 * efficiency  # noqa: F841
    desperdicio_pct = max(0.0, (1.0 - efficiency) * 100.0)

    # Enriquecer placements com polígono e metadados do molde
    parts_map: dict[str, list] = {p["id"]: p["polygon"] for p in parts}
    pecas_map: dict[str, dict] = {}
    if pecas:
        for pp in pecas:
            mid = str(pp.molde.id)
            pecas_map[mid] = {
                "peca": pp.molde.peca,
                "tamanho": pp.molde.tamanho,
                "grupo_nome": pp.molde.grupo.nome if pp.molde.grupo else None,
            }

    enriched_placements: list[dict] = []
    for pl in result["placements"]:
        mid = pl["id"]
        entry: dict = {**pl}
        if mid in parts_map:
            entry["polygon"] = parts_map[mid]
        if mid in pecas_map:
            entry.update(pecas_map[mid])
        enriched_placements.append(entry)

    mapa_json: dict = {
        "lote_id": str(tecido.lote_id) if tecido.lote_id else None,
        "tecido_id": str(tecido.tecido_id) if tecido.tecido_id else None,
        "tecido_nome": tecido.nome,
        "largura_cm": largura_cm,
        "comprimento_cm": round(width_used_cm, 3),
        "num_camadas": num_camadas,
        "efficiency": round(efficiency, 4),
        "placements": enriched_placements,
        "parts_count": sum(p["quantity"] for p in parts),
    }

    encaixe = Encaixe(
        pedido_id=pedido.id,
        lote_id=tecido.lote_id,
        tecido_id=tecido.tecido_id,
        mapa_json=mapa_json,
        comp_metros=round(comp_metros, 3),
        peso_kg=round(peso_kg, 3),
        custo_total=round(custo_total, 2),
        desperdicio_pct=round(desperdicio_pct, 2),
        num_camadas=num_camadas,
        status="ativo",
    )
    db.add(encaixe)
    db.commit()
    db.refresh(encaixe)

    return {
        "id": str(encaixe.id),
        "lote_id": str(tecido.lote_id) if tecido.lote_id else None,
        "tecido_id": str(tecido.tecido_id) if tecido.tecido_id else None,
        "tecido_nome": tecido.nome,
        "num_camadas": num_camadas,
        "comp_metros": float(encaixe.comp_metros),
        "peso_kg": float(encaixe.peso_kg),
        "custo_total": float(encaixe.custo_total),
        "desperdicio_pct": float(encaixe.desperdicio_pct),
        "total_pecas_plano": mapa_json["parts_count"],
    }


# ── Ponto de entrada público ─────────────────────────────────────────────────

def gerar_encaixe(db: Session, pedido_id: uuid.UUID) -> list[dict]:
    """Gera encaixes automáticos para todos os lotes/tecidos do pedido.

    Returns:
        Lista de dicts com resumo de cada Encaixe criado.

    Raises:
        ValueError: se o pedido não existir ou não tiver peças/tecidos.
        RuntimeError: se o motor de nesting falhar.
    """
    pedido = (
        db.query(Pedido)
        .options(
            # Nova hierarquia: lote → cor → modelo
            selectinload(Pedido.pedido_tecidos)
                .selectinload(PedidoTecido.lote)
                .selectinload(LoteTecido.cor)
                .selectinload(CorTecido.modelo),
            # Legado
            selectinload(Pedido.pedido_tecidos)
                .selectinload(PedidoTecido.tecido),
            # Peças: molde → grupo
            selectinload(Pedido.pecas)
                .selectinload(PedidoPeca.molde)
                .selectinload(Molde.grupo),
            # Peças: cor_tecido (nova hierarquia)
            selectinload(Pedido.pecas)
                .selectinload(PedidoPeca.cor_tecido),
            # Peças: tecido legado
            selectinload(Pedido.pecas)
                .selectinload(PedidoPeca.tecido),
        )
        .filter(Pedido.id == pedido_id)
        .first()
    )

    if not pedido:
        raise ValueError("Pedido não encontrado.")

    if not pedido.pecas:
        raise ValueError("O pedido não possui peças cadastradas.")

    grupos = _agrupar_por_lote_ou_tecido(pedido)

    if not grupos:
        raise ValueError(
            "Nenhuma peça possui tecido associado. "
            "Vincule ao menos um tecido ao pedido e às peças."
        )

    resultado: list[dict] = []
    for tn, pecas in grupos.values():
        encaixes = _gerar_para_tecido(db, pedido, tn, pecas)
        resultado.extend(encaixes)

    return resultado


# ── Legado: mantido para compatibilidade com chamadas existentes ─────────────

def validar_sentido_fio(rotacao_graus: float, sentido_fio: str) -> bool:
    """Valida se a rotação aplicada respeita o sentido do fio do molde."""
    tolerancia = 1.0
    angulos_permitidos: dict[str, list[float]] = {
        "vertical": [0.0, 180.0],
        "horizontal": [90.0, 270.0],
        "45graus": [45.0, 135.0, 225.0, 315.0],
    }
    permitidos = angulos_permitidos.get(sentido_fio, [0.0, 90.0, 180.0, 270.0])
    return any(abs(rotacao_graus - a) <= tolerancia for a in permitidos)
