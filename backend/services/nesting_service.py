"""nesting_service.py — Lógica de negócio para geração automática de encaixes.

Fluxo principal (gerar_encaixe):
  1. Carrega o pedido com todos os ItemPedido e seus grupo/lote vinculados.
  2. Agrupa os moldes de cada item (grupo_id + tamanho com qtd > 0) por
     lote_id (_agrupar_por_lote) — um pedido pode ter vários tecidos.
  3. Para cada lote:
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

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from models.encaixe import Encaixe
from models.grupo_molde import GrupoMolde
from models.molde import Molde
from models.pedido import ItemPedido, PedidoVenda as Pedido
from models.tecido import CorTecido, LoteTecido, ModeloTecido
from nesting.nesting_bridge import build_polygon, executar
from services.gramatura_service import aplicar_encolhimento, calcular_custo, metros_para_peso

# Comprimento máximo (cm) de um único enfesto antes de criar um segundo lote.
# 2 000 cm = 20 m (tamanho típico de mesa de corte).
MAX_ENFESTO_CM: float = 2000.0

# Multiplicador de corte por tipo_corte (mesmo mapeamento usado no pedido de venda)
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


# ── Agrupamento por lote a partir dos itens do pedido ────────────────────────

# (campo de quantidade no ItemPedido, tamanho correspondente do Molde)
TAMANHOS: list[tuple[str, str]] = [
    ("qtd_p", "P"), ("qtd_m", "M"), ("qtd_g", "G"), ("qtd_gg", "GG"),
    ("qtd_g1", "G1"), ("qtd_g2", "G2"), ("qtd_g3", "G3"),
]


def _agrupar_por_lote(
    pedido: Pedido,
) -> tuple[dict[uuid.UUID, tuple[TecidoNesting, list[tuple[Molde, int]]]], list[str]]:
    """Retorna (grupos, avisos).

    grupos: {lote_id: (TecidoNesting, [(molde, quantidade), ...])}
    avisos: mensagens legíveis sobre itens/tamanhos ignorados. Não são
    fatais por si só — cabe a gerar_encaixe decidir se viram erro (quando
    nada sobra) ou só acompanham o resultado (quando é parcial).

    Para cada ItemPedido: para cada tamanho com quantidade > 0, busca todos
    os moldes do grupo com aquele tamanho (uma peça pode ter várias partes —
    frente, costas, manga — cada uma um Molde distinto) e os agrupa pelo
    lote de tecido do item.
    """
    grupos: dict[uuid.UUID, tuple[TecidoNesting, list[tuple[Molde, int]]]] = {}
    avisos: list[str] = []

    for item in pedido.itens:
        nome_grupo = item.grupo.nome if item.grupo else str(item.grupo_id)

        if not item.lote_id or not item.lote:
            aviso = f"Peça '{nome_grupo}' sem tecido vinculado — ignorada"
            print(f"[NESTING] {aviso}")
            avisos.append(aviso)
            continue
        if not item.grupo:
            aviso = f"Item {item.id} sem grupo de moldes — ignorado"
            print(f"[NESTING] {aviso}")
            avisos.append(aviso)
            continue

        chave = item.lote_id
        if chave not in grupos:
            grupos[chave] = (TecidoNesting.de_lote(item.lote), [])
        _, pares = grupos[chave]

        for campo, tamanho in TAMANHOS:
            qtd = getattr(item, campo, 0) or 0
            if qtd <= 0:
                continue
            moldes_tamanho = [m for m in item.grupo.moldes if m.tamanho == tamanho]
            if not moldes_tamanho:
                aviso = f"Grupo '{item.grupo.nome}': sem molde tamanho={tamanho} — tamanho ignorado"
                print(f"[NESTING] {aviso}")
                avisos.append(aviso)
                continue
            for molde in moldes_tamanho:
                pares.append((molde, qtd))

    return grupos, avisos


# ── Geração de encaixes para um tecido ──────────────────────────────────────

def _gerar_para_tecido(
    db: Session,
    pedido: Pedido,
    tecido: TecidoNesting,
    pares: list[tuple[Molde, int]],
) -> tuple[list[dict], list[str]]:
    """Roda nesting para um lote de tecido e salva um ou mais Encaixes.

    Retorna (encaixes_criados, avisos).
    """
    avisos: list[str] = []

    max_qty = max(qtd for _, qtd in pares) if pares else 1
    num_camadas = max(1, min(tecido.max_camadas, max_qty))

    parts: list[dict] = []
    for molde, qtd in pares:
        mult = _MULT.get(molde.tipo_corte or "simples", 1)
        qty_plano = math.ceil(qtd * mult / num_camadas)
        if qty_plano <= 0:
            continue
        parts.append({
            "id": str(molde.id),
            "polygon": _poligono_rotacionado(molde),
            "quantity": qty_plano,
            "rotations": _rotacoes(molde.sentido_fio),
        })

    if not parts:
        return [], avisos

    largura = tecido.largura_util_cm

    result = executar(
        bin_width_cm=largura,
        bin_height_cm=MAX_ENFESTO_CM,
        parts=parts,
    )

    if not result["placements"]:
        # nest_worker descarta peças mais largas que o bin em silêncio
        # (ver nest_worker.js: findBest retorna null e o item é pulado) —
        # sem este aviso o usuário só vê 0% de aproveitamento sem saber por quê.
        avisos.append(
            f"Nenhuma peça foi posicionada no tecido '{tecido.nome}'. "
            f"Verifique se a largura útil do tecido "
            f"({tecido.largura_util_cm} cm) está correta e é maior que as "
            f"peças a encaixar."
        )

    encaixes_criados: list[dict] = []

    if result["width_used"] > MAX_ENFESTO_CM:
        encaixes_criados.extend(
            _dividir_em_lotes(db, pedido, tecido, parts, largura, num_camadas, pecas=pares)
        )
    else:
        enc = _salvar_encaixe(
            db, pedido, tecido, result, num_camadas, largura, parts, pecas=pares
        )
        encaixes_criados.append(enc)

    return encaixes_criados, avisos


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
        for molde, _qtd in pecas:
            pecas_map[str(molde.id)] = {
                "peca": molde.peca,
                "tamanho": molde.tamanho,
                "grupo_nome": molde.grupo.nome if molde.grupo else None,
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

    # Numeração sequencial própria do encaixe (ENC-001, ENC-002...) —
    # recalculada a cada chamada, então cada Encaixe criado dentro do mesmo
    # gerar_encaixe() (um por lote/tecido) recebe o próximo número, já que
    # o commit logo abaixo torna este encaixe visível ao COUNT(*) seguinte.
    proximo_numero = db.query(func.count(Encaixe.id)).scalar() + 1

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
        numero=proximo_numero,
        descricao=pedido.observacoes_internas,
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
        "numero_enc": encaixe.numero,
        "descricao": encaixe.descricao,
    }


# ── Ponto de entrada público ─────────────────────────────────────────────────

def gerar_encaixe(db: Session, pedido_id: uuid.UUID) -> dict:
    """Gera encaixes automáticos para todos os lotes de tecido do pedido.

    Returns:
        {"encaixes": [...resumo de cada Encaixe criado...], "avisos": [...]}
        — avisos cobre itens/tamanhos ignorados que não impediram a geração.

    Raises:
        ValueError: se o pedido não existir, não tiver itens, ou se nenhuma
            peça pôde ser agrupada (todas sem tecido/molde válido).
        RuntimeError: se o motor de nesting falhar.
    """
    pedido = (
        db.query(Pedido)
        .options(
            selectinload(Pedido.itens)
                .selectinload(ItemPedido.grupo)
                .selectinload(GrupoMolde.moldes),
            selectinload(Pedido.itens)
                .selectinload(ItemPedido.lote)
                .selectinload(LoteTecido.cor)
                .selectinload(CorTecido.modelo),
        )
        .filter(Pedido.id == pedido_id)
        .first()
    )

    if not pedido:
        raise ValueError("Pedido não encontrado.")

    if not pedido.itens:
        raise ValueError("O pedido não possui itens cadastrados.")

    grupos, avisos = _agrupar_por_lote(pedido)

    if not grupos:
        raise ValueError(
            "Nenhuma peça foi vinculada a um tecido. "
            "Selecione um tecido para cada peça antes de gerar o encaixe."
        )

    resultado: list[dict] = []
    for tecido, pares in grupos.values():
        encaixes, avisos_tecido = _gerar_para_tecido(db, pedido, tecido, pares)
        resultado.extend(encaixes)
        avisos.extend(avisos_tecido)

    return {"encaixes": resultado, "avisos": avisos}


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
