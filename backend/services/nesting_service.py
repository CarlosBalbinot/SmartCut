"""nesting_service.py — Lógica de negócio para geração automática de encaixes.

Fluxo (gerar_de_entradas — comum ao Encaixe Rápido e à Ordem de Corte):
  1. Recebe a lista neutra de entradas (lote, molde, quantidade), montada
     por montar_pares_legado (Encaixe Rápido) ou
     ordem_corte_service.montar_pares_oc (OC).
  2. Agrupa por lote de tecido (_agrupar_por_lote).
  3. Para cada lote:
       a. Planeja os enfestos (services/plano_enfesto.py): camadas e
          conjuntos de cada tamanho, no modo SEM_SOBRA ou MENOS_ENFESTOS.
       b. Para cada enfesto, monta os polígonos para o worker (conjuntos ×
          multiplicador de tipo_corte) e chama nesting_bridge.executar().
       c. Se o risco passa do comprimento máximo (mesa de corte), divide
          as peças em partes <= limite, cada uma um encaixe com as mesmas
          camadas (_partes_do_enfesto).
       d. Calcula comp_metros, peso_kg, custo_total e desperdicio_pct com
          aplicação do encolhimento e monta o Encaixe na sessão (sem gravar).
  4. Numera (MAX+1) e grava todos os encaixes num único commit — erro em
     qualquer lote descarta tudo.
  5. Retorna os resumos dos encaixes, avisos e o plano de cada lote.
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from models.encaixe import Encaixe
from models.grupo_molde import GrupoMolde
from models.molde import Molde
from models.ordem_corte import COMPRIMENTO_MAX_PADRAO_CM
from models.pedido import ItemPedido, PedidoVenda as Pedido
from models.tecido import CorTecido, LoteTecido, ModeloTecido
from nesting.nesting_bridge import build_polygon, executar
from services.gramatura_service import aplicar_encolhimento, calcular_custo, metros_para_peso
from services.plano_enfesto import linhas_enfesto, planejar

logger = logging.getLogger(__name__)

# Multiplicador de corte por tipo_corte (mesmo mapeamento usado no pedido de venda)
_MULT: dict[str, int] = {"simples": 1, "par": 2, "par_sem_espelho": 2}

# Folga (cm) nas comparações com o limite: o topo da peça é recalculado aqui
# com a mesma conta do worker, mas cos/sin do V8 e do CPython podem diferir
# no último bit.
_EPS_CM = 1e-3


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
    lote_id: uuid.UUID | None  # nova hierarquia
    tecido_id: uuid.UUID | None  # legado

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
    return [[cx + (x - cx) * cos_a - (y - cy) * sin_a, cy + (x - cx) * sin_a + (y - cy) * cos_a] for x, y in pts]


def _poligono_rotacionado(molde: Molde) -> list[list[float]]:
    """Extrai o polígono e aplica rotacao_base antes de passar ao nesting."""
    pts = _poligono(molde)
    return _rotate_polygon(pts, molde.rotacao_base or 0)


# ── Entrada neutra ───────────────────────────────────────────────────────────
#
# Toda geração parte de uma lista neutra de entradas (lote, molde, quantidade)
# — uma entrada por PARTE do molde (frente, costas…) com a quantidade de
# peças inteiras daquele tamanho. Quem monta a lista:
#   montar_pares_legado(pedido)          → Encaixe Rápido (grupo_id/lote_id/qtd_*)
#   ordem_corte_service.montar_pares_oc  → Ordem de Corte (SKU → molde + lote da OC)

Entrada = tuple[LoteTecido, Molde, int]

# (campo de quantidade no ItemPedido, tamanho correspondente do Molde)
TAMANHOS: list[tuple[str, str]] = [
    ("qtd_p", "P"),
    ("qtd_m", "M"),
    ("qtd_g", "G"),
    ("qtd_gg", "GG"),
    ("qtd_g1", "G1"),
    ("qtd_g2", "G2"),
    ("qtd_g3", "G3"),
]


def _norm(texto: str | None) -> str:
    return (texto or "").strip().casefold()


def montar_pares_legado(pedido: Pedido) -> tuple[list[Entrada], list[str]]:
    """Formato do Encaixe Rápido: ItemPedido com grupo_id, lote_id e
    qtd_p..qtd_g3. Itens/tamanhos ignorados viram aviso."""
    entradas: list[Entrada] = []
    avisos: list[str] = []

    for item in pedido.itens:
        nome_grupo = item.grupo.nome if item.grupo else str(item.grupo_id)
        if not item.lote_id or not item.lote:
            avisos.append(f"Peça '{nome_grupo}' sem tecido vinculado — ignorada")
            continue
        if not item.grupo:
            avisos.append(f"Item {item.numero_item:03d} sem grupo de moldes — ignorado")
            continue
        for campo, tamanho in TAMANHOS:
            qtd = getattr(item, campo, 0) or 0
            if qtd <= 0:
                continue
            moldes = [m for m in item.grupo.moldes if _norm(m.tamanho) == _norm(tamanho)]
            if not moldes:
                avisos.append(f"Grupo '{item.grupo.nome}': sem molde tamanho={tamanho} — tamanho ignorado")
                continue
            entradas.extend((item.lote, molde, qtd) for molde in moldes)

    return entradas, avisos


def _agrupar_por_lote(
    entradas: list[Entrada],
) -> dict[uuid.UUID, tuple[TecidoNesting, dict[uuid.UUID, list]]]:
    """{lote_id: (TecidoNesting, {molde_id: [molde, quantidade]})} — a mesma
    parte vinda de itens diferentes (ex.: duas cores no mesmo lote) soma."""
    grupos: dict[uuid.UUID, tuple[TecidoNesting, dict[uuid.UUID, list]]] = {}
    for lote, molde, qtd in entradas:
        if qtd <= 0:
            continue
        if lote.id not in grupos:
            grupos[lote.id] = (TecidoNesting.de_lote(lote), {})
        moldes = grupos[lote.id][1]
        if molde.id in moldes:
            moldes[molde.id][1] += qtd
        else:
            moldes[molde.id] = [molde, qtd]
    return grupos


# ── Geração de encaixes para um lote ─────────────────────────────────────────


def _chave(molde: Molde) -> tuple:
    """Identifica a peça inteira: grupo de moldes + tamanho."""
    return (molde.grupo_id, _norm(molde.tamanho))


def _rotulo(moldes_da_chave: list[Molde]) -> dict:
    m = moldes_da_chave[0]
    return {"grupo_nome": m.grupo.nome if m.grupo else None, "tamanho": (m.tamanho or "").strip()}


def _gerar_para_tecido(
    db: Session,
    pedido: Pedido,
    tecido: TecidoNesting,
    moldes_qtd: dict[uuid.UUID, list],
    modo: str,
    ordem_corte_id: uuid.UUID | None,
    descricao: str | None,
    limite_cm: int,
) -> tuple[list[Encaixe], list[str], dict]:
    """Planeja os enfestos do lote (plano_enfesto) e roda o nesting de cada
    um — cada enfesto vira um Encaixe, ou várias partes (todas <= limite_cm,
    mesmas camadas) quando o risco não cabe na mesa. Tudo adicionado à
    sessão sem número e sem commit.

    Retorna (encaixes_montados, avisos, plano).
    """
    avisos: list[str] = []

    por_chave: dict[tuple, list[Molde]] = {}
    qtd_chave: dict[tuple, int] = {}
    for molde, qtd in moldes_qtd.values():
        k = _chave(molde)
        por_chave.setdefault(k, []).append(molde)
        qtd_chave[k] = max(qtd_chave.get(k, 0), qtd)

    plano = planejar(qtd_chave, tecido.max_camadas, modo)
    rotulos = {k: _rotulo(ms) for k, ms in por_chave.items()}
    todos_moldes = [m for m, _ in moldes_qtd.values()]
    moldes_por_id = {str(m.id): m for m in todos_moldes}
    pares = {i for i, m in moldes_por_id.items() if _MULT.get(m.tipo_corte or "simples", 1) > 1}
    encaixes: list[Encaixe] = []

    for n, enfesto in enumerate(plano["enfestos"], start=1):
        camadas = enfesto["camadas"]
        parts: list[dict] = []
        for k, conjuntos in enfesto["conjuntos_por_tamanho"].items():
            for molde in por_chave[k]:
                parts.append(
                    {
                        "id": str(molde.id),
                        "polygon": _poligono_rotacionado(molde),
                        "quantity": conjuntos * _MULT.get(molde.tipo_corte or "simples", 1),
                        "rotations": _rotacoes(molde.sentido_fio),
                    }
                )
        if not parts:
            continue

        extras = {
            "modo_camadas": modo,
            "enfesto": n,
            "total_enfestos": len(plano["enfestos"]),
            "pecas_por_tamanho": linhas_enfesto(enfesto, rotulos),
            "sobra_total": sum(enfesto["sobra_por_tamanho"].values()),
        }
        largura = tecido.largura_util_cm
        partes, avisos_partes = _partes_do_enfesto(parts, largura, limite_cm, pares, moldes_por_id)
        avisos.extend(avisos_partes)

        if not partes[0][0]["placements"]:
            # nest_worker descarta peças mais largas que o bin em silêncio
            # (ver nest_worker.js: findBest retorna null e o item é pulado) —
            # sem este aviso o usuário só vê 0% de aproveitamento sem saber por quê.
            avisos.append(
                f"Nenhuma peça foi posicionada no tecido '{tecido.nome}'. "
                f"Verifique se a largura útil do tecido "
                f"({tecido.largura_util_cm} cm) está correta e é maior que as "
                f"peças a encaixar."
            )

        total = len(partes)
        for i, (result_parte, parts_parte) in enumerate(partes, start=1):
            if result_parte["width_used"] > limite_cm + _EPS_CM and not avisos_partes:
                # Sem peça maior que o limite: passou por causa de um par
                # que só cabe junto acima da mesa.
                avisos.append(
                    f"Enfesto {n}, parte {i}: {result_parte['width_used']:.1f} cm, acima do limite de {limite_cm} cm."
                )
            # "parte" (texto 2/3) só quando dividido — é o que a tela e o
            # formulário exibem; parte_numero/total_partes sempre.
            extras_parte = {
                **extras,
                "comprimento_max_cm": limite_cm,
                "parte_numero": i,
                "total_partes": total,
                "pecas_parte": _pecas_parte(parts_parte, moldes_por_id, camadas),
            }
            if total > 1:
                extras_parte["parte"] = f"{i}/{total}"
            encaixes.append(
                _montar_encaixe(
                    db,
                    pedido,
                    tecido,
                    result_parte,
                    camadas,
                    largura,
                    parts_parte,
                    pecas=todos_moldes,
                    extras=extras_parte,
                    ordem_corte_id=ordem_corte_id,
                    descricao=descricao,
                )
            )

    # A mesma peça grande em vários enfestos gera o mesmo aviso — uma vez só.
    return encaixes, list(dict.fromkeys(avisos)), plano


# ── Divisão do enfesto em partes (comprimento máximo) ────────────────────────
#
# O nest_worker ignora bin.height: empilha tudo num risco só e não devolve
# as peças que "não couberam". A divisão é feita aqui, sem mexer no worker:
#   1. encaixa as peças restantes;
#   2. a parte fica com as peças cujo topo (y + altura na rotação escolhida)
#      está dentro do limite — posições válidas, o worker só as empilha;
#   3. as demais voltam para o passo 1 como a próxima parte.
# Cada peça sai em exatamente uma parte (nada repetido, nada faltando).


def _dimensoes(poligono: list[list[float]], graus: float) -> tuple[float, float]:
    """(largura, comprimento) do bounding box após a rotação — mesma conta
    do rotatedBBox do nest_worker (rotação em torno da origem)."""
    rad = graus * math.pi / 180
    c, s = math.cos(rad), math.sin(rad)
    xs = [x * c - y * s for x, y in poligono]
    ys = [x * s + y * c for x, y in poligono]
    return max(xs) - min(xs), max(ys) - min(ys)


def _area(poligono: list[list[float]]) -> float:
    n = len(poligono)
    dobro = sum(poligono[i][0] * poligono[(i + 1) % n][1] - poligono[(i + 1) % n][0] * poligono[i][1] for i in range(n))
    return abs(dobro) / 2


def _nome_molde(molde: Molde | None) -> str:
    if molde is None:
        return "?"
    return (molde.nome or f"{molde.peca or ''} {molde.tamanho or ''}").strip()


def _fechar_pares(manter: list[int], placements: list[dict], topos: list[float], pares: set[str]) -> list[int]:
    """Peça em par (tipo_corte par) fica inteira na mesma parte: com número
    ímpar de cópias na parte, a mais alta volta para a próxima. Se a parte
    ficar vazia (só havia meio par), puxa o par dela — a parte passa do
    limite e o chamador avisa."""
    manter = sorted(manter, key=lambda i: topos[i])
    for pid in pares:
        do_id = [i for i in manter if placements[i]["id"] == pid]
        if len(do_id) % 2:
            manter.remove(do_id[-1])
    if manter:
        return manter
    primeiro = min(range(len(placements)), key=lambda i: topos[i])
    manter = [primeiro]
    pid = placements[primeiro]["id"]
    if pid in pares:
        outros = [i for i in range(len(placements)) if placements[i]["id"] == pid and i != primeiro]
        manter += sorted(outros, key=lambda i: topos[i])[:1]
    return manter


def _partes_do_enfesto(
    parts: list[dict],
    largura: float,
    limite_cm: float,
    pares: set[str],
    moldes_por_id: dict[str, Molde],
) -> tuple[list[tuple[dict, list[dict]]], list[str]]:
    """Divide o enfesto em partes de comprimento <= limite_cm.

    Retorna ([(result, parts_da_parte)], avisos) — result no formato do
    worker (placements, efficiency, width_used). Risco que cabe no limite
    sai numa parte só, com o resultado do worker intacto (mesmo resultado
    de antes do limite); a última parte tem o comprimento real usado.
    """
    por_id = {p["id"]: p for p in parts}
    avisos: list[str] = []
    for p in parts:
        dims = [_dimensoes(p["polygon"], r) for r in p["rotations"] or [0]]
        cabem = [comp for larg, comp in dims if larg <= largura + _EPS_CM]
        if cabem and min(cabem) > limite_cm + _EPS_CM:
            avisos.append(
                f"Peça {_nome_molde(moldes_por_id.get(p['id']))} ({min(cabem):.1f} cm) "
                f"maior que o limite de {limite_cm:g} cm"
            )

    restante = {p["id"]: p["quantity"] for p in parts}
    partes: list[tuple[dict, list[dict]]] = []
    while any(restante.values()):
        lote = [{**por_id[i], "quantity": q} for i, q in restante.items() if q > 0]
        result = executar(bin_width_cm=largura, bin_height_cm=limite_cm, parts=lote)
        pls = result["placements"]
        if not pls:
            if not partes:
                partes.append((result, lote))  # nada coube na largura — o chamador avisa
            else:
                avisos.append(
                    f"{sum(restante.values())} peça(s) mais largas que o tecido ({largura:g} cm) não foram encaixadas."
                )
            break

        topos = [pl["y"] + _dimensoes(por_id[pl["id"]]["polygon"], pl["rotation"])[1] for pl in pls]
        if max(topos) <= limite_cm + _EPS_CM:
            manter = list(range(len(pls)))
        else:
            dentro = [i for i, t in enumerate(topos) if t <= limite_cm + _EPS_CM]
            manter = _fechar_pares(dentro, pls, topos, pares)

        contagem: dict[str, int] = {}
        for i in manter:
            contagem[pls[i]["id"]] = contagem.get(pls[i]["id"], 0) + 1
        for pid, qtd in contagem.items():
            restante[pid] -= qtd
        parts_parte = [{**por_id[pid], "quantity": qtd} for pid, qtd in contagem.items()]

        if len(manter) == len(pls):
            partes.append((result, parts_parte))
            continue
        comprimento = max(topos[i] for i in manter)
        area = sum(_area(por_id[pls[i]["id"]]["polygon"]) for i in manter)
        eficiencia = min(area / (largura * comprimento), 1.0) if comprimento > 0 else 0.0
        parcial = {
            "placements": [pls[i] for i in sorted(manter)],
            "efficiency": round(eficiencia, 4),
            "width_used": round(comprimento, 3),
        }
        partes.append((parcial, parts_parte))
    return partes, avisos


def _pecas_parte(parts_parte: list[dict], moldes_por_id: dict[str, Molde], camadas: int) -> list[dict]:
    """Peças (moldes) desta parte: pecas_por_tamanho continua sendo do
    enfesto inteiro; aqui está o que cada parte corta de fato."""
    saida = []
    for p in parts_parte:
        m = moldes_por_id.get(p["id"])
        saida.append(
            {
                "molde_id": p["id"],
                "peca": m.peca if m else None,
                "grupo_nome": m.grupo.nome if m and m.grupo else None,
                "tamanho": (m.tamanho or "").strip() if m else None,
                "por_camada": p["quantity"],
                "total": p["quantity"] * camadas,
            }
        )
    return saida


def _montar_encaixe(
    db: Session,
    pedido: Pedido,
    tecido: TecidoNesting,
    result: dict,
    num_camadas: int,
    largura_cm: float,
    parts: list[dict],
    pecas: list[Molde] | None = None,
    extras: dict | None = None,
    ordem_corte_id: uuid.UUID | None = None,
    descricao: str | None = None,
) -> Encaixe:
    """Calcula métricas e adiciona o Encaixe à sessão — sem flush/commit e
    sem número: gerar_de_entradas numera e grava todos juntos numa transação.

    peso_kg/custo_total são de UMA camada (comprimento do encaixe);
    mapa_json.peso_total_kg = peso_kg × camadas (consumo real do lote)."""

    width_used_cm: float = result["width_used"]
    efficiency: float = result["efficiency"]

    comp_minimo_m = width_used_cm / 100.0
    comp_metros = aplicar_encolhimento(comp_minimo_m, tecido.encolhimento_pct)
    peso_kg = metros_para_peso(comp_metros, tecido.gramatura_g_m2, largura_cm)
    custo_total = calcular_custo(peso_kg, tecido.valor_por_kg)

    desperdicio_pct = max(0.0, (1.0 - efficiency) * 100.0)

    # Enriquecer placements com polígono e metadados do molde
    parts_map: dict[str, list] = {p["id"]: p["polygon"] for p in parts}
    pecas_map: dict[str, dict] = {}
    for molde in pecas or []:
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
        "peso_total_kg": round(peso_kg * num_camadas, 3),
        **(extras or {}),
    }

    # id explícito: o resumo devolvido ao frontend precisa dele antes do
    # flush (o default do model só é aplicado na gravação).
    encaixe = Encaixe(
        id=uuid.uuid4(),
        pedido_id=pedido.id,
        ordem_corte_id=ordem_corte_id,
        lote_id=tecido.lote_id,
        mapa_json=mapa_json,
        comp_metros=round(comp_metros, 3),
        peso_kg=round(peso_kg, 3),
        custo_total=round(custo_total, 2),
        desperdicio_pct=round(desperdicio_pct, 2),
        num_camadas=num_camadas,
        status="ativo",
        descricao=descricao,
    )
    db.add(encaixe)
    return encaixe


# ── Numeração e gravação ─────────────────────────────────────────────────────

# Tentativas de gravação quando outra geração simultânea pega o mesmo número
# (a UNIQUE uq_encaixes_numero rejeita o segundo commit).
_TENTATIVAS_NUMERACAO = 3


def _numerar(db: Session, encaixes: list[Encaixe]) -> None:
    """ENC-XXX = MAX(numero)+1 sobre TODOS os encaixes, inclusive os
    deletados (soft-delete), para nunca reaproveitar um número. A sessão
    roda com autoflush=False, então os encaixes pendentes desta chamada
    não entram no MAX."""
    ultimo = db.query(func.max(Encaixe.numero)).scalar() or 0
    for i, encaixe in enumerate(encaixes, start=1):
        encaixe.numero = ultimo + i


def _gravar(db: Session, encaixes: list[Encaixe]) -> None:
    """Numera e grava todos os encaixes da chamada num único commit — junto
    com o que mais estiver pendente na sessão (ex.: encaixes anteriores da
    OC marcados como deletados)."""
    for tentativa in range(1, _TENTATIVAS_NUMERACAO + 1):
        _numerar(db, encaixes)
        try:
            db.commit()
            return
        except IntegrityError:
            db.rollback()
            if tentativa == _TENTATIVAS_NUMERACAO:
                raise
            # O rollback expulsa os objetos pendentes da sessão — readiciona
            # e tenta de novo com o MAX atualizado.
            db.add_all(encaixes)


def _resumo(encaixe: Encaixe) -> dict:
    mapa = encaixe.mapa_json or {}
    return {
        "id": str(encaixe.id),
        "lote_id": mapa.get("lote_id"),
        "tecido_id": mapa.get("tecido_id"),
        "tecido_nome": mapa.get("tecido_nome"),
        "num_camadas": encaixe.num_camadas,
        "comp_metros": float(encaixe.comp_metros),
        "peso_kg": float(encaixe.peso_kg),
        "peso_total_kg": mapa.get("peso_total_kg") or round(float(encaixe.peso_kg) * (encaixe.num_camadas or 1), 3),
        "custo_total": float(encaixe.custo_total),
        "custo_total_camadas": round(float(encaixe.custo_total) * (encaixe.num_camadas or 1), 2),
        "desperdicio_pct": float(encaixe.desperdicio_pct),
        "aproveitamento_pct": round(100.0 - float(encaixe.desperdicio_pct), 2),
        "total_pecas_plano": mapa.get("parts_count"),
        "enfesto": mapa.get("enfesto"),
        "parte": mapa.get("parte"),
        "parte_numero": mapa.get("parte_numero"),
        "total_partes": mapa.get("total_partes"),
        "comprimento_max_cm": mapa.get("comprimento_max_cm"),
        "pecas_parte": mapa.get("pecas_parte"),
        "pecas_por_tamanho": mapa.get("pecas_por_tamanho"),
        "sobra_total": mapa.get("sobra_total"),
        "numero_enc": encaixe.numero,
        "descricao": encaixe.descricao,
    }


# ── Pontos de entrada públicos ───────────────────────────────────────────────


def gerar_de_entradas(
    db: Session,
    pedido: Pedido,
    entradas: list[Entrada],
    *,
    modo: str,
    ordem_corte_id: uuid.UUID | None = None,
    descricao: str | None = None,
    comprimento_max_cm: int = COMPRIMENTO_MAX_PADRAO_CM,
) -> dict:
    """Núcleo comum: agrupa as entradas por lote, planeja os enfestos, roda o
    nesting e grava tudo numa transação — erro em qualquer lote desfaz tudo
    (inclusive o que o chamador deixou pendente na sessão).

    comprimento_max_cm: limite de cada encaixe (mesa de corte) — risco maior
    é dividido em partes (_partes_do_enfesto).

    Returns: {"encaixes": [...resumos], "avisos": [...], "planos": {lote_id: plano}}
    Raises: ValueError se nenhuma entrada tiver quantidade; RuntimeError
        se o motor de nesting falhar.
    """
    grupos = _agrupar_por_lote(entradas)
    if not grupos:
        db.rollback()
        raise ValueError("Nenhuma peça para encaixar: verifique tecidos, moldes e quantidades.")

    encaixes: list[Encaixe] = []
    avisos: list[str] = []
    planos: dict[str, dict] = {}
    try:
        for lote_id, (tecido, moldes_qtd) in grupos.items():
            montados, avisos_lote, plano = _gerar_para_tecido(
                db, pedido, tecido, moldes_qtd, modo, ordem_corte_id, descricao, comprimento_max_cm
            )
            encaixes.extend(montados)
            avisos.extend(avisos_lote)
            planos[str(lote_id)] = plano
        if encaixes:
            _gravar(db, encaixes)
    except Exception:
        db.rollback()
        raise

    return {"encaixes": [_resumo(e) for e in encaixes], "avisos": avisos, "planos": planos}


def gerar_encaixe(db: Session, pedido_id: uuid.UUID, comprimento_max_cm: int = COMPRIMENTO_MAX_PADRAO_CM) -> dict:
    """Encaixe Rápido: gera encaixes para todos os lotes do pedido interno
    (formato legado). Mantém a regra antiga de camadas (MENOS_ENFESTOS: um
    enfesto por lote, camadas = min(max_camadas, maior quantidade)) e divide
    em partes o risco que passar de comprimento_max_cm.

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
            selectinload(Pedido.itens).selectinload(ItemPedido.grupo).selectinload(GrupoMolde.moldes),
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

    entradas, avisos = montar_pares_legado(pedido)
    for aviso in avisos:
        logger.info("[NESTING] %s", aviso)

    if not entradas:
        raise ValueError(
            "Nenhuma peça foi vinculada a um tecido. Selecione um tecido para cada peça antes de gerar o encaixe."
        )

    resultado = gerar_de_entradas(
        db,
        pedido,
        entradas,
        modo="MENOS_ENFESTOS",
        descricao=pedido.observacoes_internas,
        comprimento_max_cm=comprimento_max_cm,
    )
    return {"encaixes": resultado["encaixes"], "avisos": avisos + resultado["avisos"]}
