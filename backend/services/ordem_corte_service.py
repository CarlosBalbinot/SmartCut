"""Ordem de Corte (OC) — criação a partir do pedido, conferência e edição.

Resolução de molde de cada item (SKU da grade produto pai × linha × coluna):
    SKU → produto_pai_id → GrupoMolde.produto_id → Molde.tamanho
    com Molde.tamanho == descrição da coluna do SKU (trim + case-insensitive).

A OC guarda um snapshot dos itens do pedido; pedido_hash é a assinatura
desses itens e acusa quando o pedido mudou depois (desatualizada).
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from models.encaixe import Encaixe, EncaixeCamada
from models.grupo_molde import GrupoMolde
from models.ordem_corte import (
    COMPRIMENTO_MAX_MAX_CM,
    COMPRIMENTO_MAX_MIN_CM,
    MODOS_CAMADAS,
    ORGANIZAR_POR,
    QUALIDADES,
    TIPOS_ENFESTO,
    ItemOrdemCorte,
    OrdemCorte,
    OrdemCorteTecido,
)
from models.pedido import ItemPedido, PedidoVenda
from models.produto_sku import ProdutoSKU
from models.tecido import ConsumoLote, CorTecido, LoteTecido
from services import lote_service, nesting_service
from services.erros import ERRO, ErroApp
from services.plano_enfesto import linhas_enfesto, planejar

logger = logging.getLogger(__name__)

# Status em que a OC ainda aceita mudanças de itens, tecidos e modo.
_EDITAVEL = "RASCUNHO"
_FINAIS = ("CONCLUIDA", "CANCELADA")
_LOTE_INDISPONIVEL = ("arquivado", "esgotado")
# Status que travam o lote: enquanto a OC está aqui, o peso planejado dela
# fica reservado e não pode ser planejado por outra OC.
_RESERVANDO = ("ENVIADA", "EM_CORTE")


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class ErroOC(ErroApp):
    """Regra de negócio da OC violada (handler → HTTP `status`)."""

    def __init__(self, mensagem: str, status: int = 400, codigo: str = ERRO, **params):
        super().__init__(codigo, mensagem, status, **params)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _norm(texto: str | None) -> str:
    return (texto or "").strip().casefold()


def numero_fmt(numero: int | None) -> str:
    return f"OC-{numero:04d}" if numero is not None else "OC-—"


def moldes_do_tamanho(grupo: GrupoMolde | None, tamanho: str | None) -> list:
    """Moldes (uma parte cada: frente, costas…) do grupo para o tamanho."""
    if not grupo or not _norm(tamanho):
        return []
    alvo = _norm(tamanho)
    return [m for m in grupo.moldes if _norm(m.tamanho) == alvo]


def _itens_pedido(db: Session, pedido_id: uuid.UUID) -> list[ItemPedido]:
    return (
        db.execute(
            select(ItemPedido)
            .where(ItemPedido.pedido_id == pedido_id)
            .options(
                selectinload(ItemPedido.sku).selectinload(ProdutoSKU.linha_item),
                selectinload(ItemPedido.sku).selectinload(ProdutoSKU.coluna_item),
            )
            .order_by(ItemPedido.numero_item)
        )
        .scalars()
        .all()
    )


def _hash_itens(itens: list[ItemPedido]) -> str:
    """Assinatura dos itens do pedido que entram na OC (id, produto, SKU,
    quantidade) — muda ao incluir/remover item, trocar SKU ou quantidade."""
    partes = sorted(f"{i.id}|{i.produto_id}|{i.sku_id}|{i.quantidade or 0}" for i in itens if i.produto_id is not None)
    return hashlib.sha256("\n".join(partes).encode()).hexdigest()


def hash_pedido(db: Session, pedido_id: uuid.UUID) -> str:
    return _hash_itens(_itens_pedido(db, pedido_id))


def desatualizada(db: Session, oc: OrdemCorte) -> bool:
    return hash_pedido(db, oc.pedido_id) != oc.pedido_hash


# Marca gravada no mapa_json dos encaixes quando o comprimento máximo da OC
# muda depois de gerados — some ao regerar (os encaixes novos não a têm).
_MARCA_LIMITE = "limite_desatualizado"


def encaixes_desatualizados(oc: OrdemCorte) -> bool:
    """Encaixes do RASCUNHO gerados antes da última mudança do comprimento
    máximo — exigem regerar antes de enviar."""
    if oc.status != _EDITAVEL:
        return False
    return any((e.mapa_json or {}).get(_MARCA_LIMITE) for e in oc.encaixes if e.status != "deletado")


def _grupos_por_produto(db: Session, produto_ids: set[uuid.UUID]) -> dict[uuid.UUID, GrupoMolde]:
    """GrupoMolde vinculado a cada produto pai (o mais antigo, se houver
    mais de um), com os moldes carregados."""
    if not produto_ids:
        return {}
    grupos = (
        db.execute(
            select(GrupoMolde)
            .where(GrupoMolde.produto_id.in_(produto_ids))
            .options(selectinload(GrupoMolde.moldes))
            .order_by(GrupoMolde.criado_em)
        )
        .scalars()
        .all()
    )
    mapa: dict[uuid.UUID, GrupoMolde] = {}
    for g in grupos:
        mapa.setdefault(g.produto_id, g)
    return mapa


def _snapshot(db: Session, oc: OrdemCorte, itens_pedido: list[ItemPedido]) -> None:
    """(Re)cria os itens da OC a partir dos itens do pedido e ajusta as
    linhas de tecido: mantém as escolhas de (produto, cor) que continuam,
    cria as novas e remove as que sumiram."""
    elegiveis = [i for i in itens_pedido if i.produto_id is not None]
    pais: list[uuid.UUID] = [i.sku.produto_pai_id if i.sku else i.produto_id for i in elegiveis]
    grupos = _grupos_por_produto(db, set(pais))

    oc.itens.clear()
    chaves: list[tuple[uuid.UUID, str | None]] = []
    for item, pai in zip(elegiveis, pais):
        sku = item.sku
        cor = sku.linha_item.descricao if sku and sku.linha_item else None
        tamanho = sku.coluna_item.descricao if sku and sku.coluna_item else None
        grupo = grupos.get(pai)
        oc.itens.append(
            ItemOrdemCorte(
                item_pedido_id=item.id,
                numero_item=item.numero_item,
                sku_id=item.sku_id,
                produto_pai_id=pai,
                cor=cor,
                tamanho=tamanho,
                quantidade=item.quantidade or 0,
                grupo_molde_id=grupo.id if grupo else None,
            )
        )
        if (pai, cor) not in chaves:
            chaves.append((pai, cor))

    existentes = {(t.produto_pai_id, t.cor): t for t in oc.tecidos}
    for chave, tecido in existentes.items():
        if chave not in chaves:
            oc.tecidos.remove(tecido)
    for pai, cor in chaves:
        if (pai, cor) not in existentes:
            oc.tecidos.append(OrdemCorteTecido(produto_pai_id=pai, cor=cor))

    oc.pedido_hash = _hash_itens(itens_pedido)


def _carregar(db: Session, oc_id: uuid.UUID) -> OrdemCorte | None:
    return (
        db.execute(
            select(OrdemCorte)
            .where(OrdemCorte.id == oc_id)
            .options(
                selectinload(OrdemCorte.pedido),
                selectinload(OrdemCorte.itens).selectinload(ItemOrdemCorte.sku),
                selectinload(OrdemCorte.itens).selectinload(ItemOrdemCorte.produto_pai),
                selectinload(OrdemCorte.itens).selectinload(ItemOrdemCorte.grupo_molde),
                selectinload(OrdemCorte.tecidos).selectinload(OrdemCorteTecido.produto_pai),
                selectinload(OrdemCorte.tecidos)
                .selectinload(OrdemCorteTecido.lote)
                .selectinload(LoteTecido.cor)
                .selectinload(CorTecido.modelo),
                selectinload(OrdemCorte.encaixes),
            )
        )
        .scalars()
        .first()
    )


def _obter_editavel(db: Session, oc_id: uuid.UUID) -> OrdemCorte:
    oc = _carregar(db, oc_id)
    if not oc:
        raise ErroOC("Ordem de Corte não encontrada", 404)
    if oc.status != _EDITAVEL:
        raise ErroOC(f"Ordem de Corte em {oc.status} não pode ser alterada (só em RASCUNHO).", 409)
    return oc


def oc_ativa_do_pedido(db: Session, pedido_id: uuid.UUID) -> OrdemCorte | None:
    return (
        db.execute(select(OrdemCorte).where(OrdemCorte.pedido_id == pedido_id, OrdemCorte.status != "CANCELADA"))
        .scalars()
        .first()
    )


# ── Conferência ───────────────────────────────────────────────────────────────


def conferir(db: Session, oc: OrdemCorte) -> list[dict]:
    """Pendências da OC. `bloqueia` = impede gerar encaixes.

    O GrupoMolde é resolvido de novo aqui (não do snapshot): vincular um
    grupo ou cadastrar um molde depois da geração já some com a pendência.
    """
    pendencias: list[dict] = []
    grupos = _grupos_por_produto(db, {i.produto_pai_id for i in oc.itens})
    # Lote escolhido de cada (produto, cor) — o mesmo vínculo de montar_pares_oc.
    lotes = {(t.produto_pai_id, _norm(t.cor)): t.lote for t in oc.tecidos if t.lote}

    def _add(codigo: str, mensagem: str, bloqueia: bool = True, **extra) -> None:
        pendencias.append({"codigo": codigo, "mensagem": mensagem, "bloqueia": bloqueia, **extra})

    sem_grupo: dict[uuid.UUID, list[int]] = {}
    sem_molde: dict[tuple[uuid.UUID, str], list[int]] = {}
    # Problemas de geometria/largura/comprimento das peças (Tarefa 2) — a
    # mensagem já cita molde e tecido; junta os itens afetados por pendência.
    geo_problemas: dict[tuple[str, str], dict] = {}
    for item in oc.itens:
        produto = item.produto_pai
        nome = produto.descricao if produto else str(item.produto_pai_id)
        if not _norm(item.tamanho):
            _add(
                "GRADE_SEM_TAMANHO",
                f"Item {item.numero_item:03d} ({nome}): SKU sem coluna de tamanho na grade.",
                numero_itens=[item.numero_item],
                produto_pai_id=str(item.produto_pai_id),
            )
            continue
        grupo = grupos.get(item.produto_pai_id)
        if not grupo:
            sem_grupo.setdefault(item.produto_pai_id, []).append(item.numero_item)
            continue
        moldes = moldes_do_tamanho(grupo, item.tamanho)
        if not moldes:
            sem_molde.setdefault((item.produto_pai_id, item.tamanho.strip()), []).append(item.numero_item)
            continue
        lote = lotes.get((item.produto_pai_id, _norm(item.cor)))
        for molde in moldes:
            for codigo, mensagem, bloqueia in nesting_service.checar_molde(molde, lote, oc.comprimento_max_cm):
                dado = geo_problemas.setdefault((codigo, mensagem), {"bloqueia": bloqueia, "numero_itens": set()})
                dado["numero_itens"].add(item.numero_item)

    nomes = {i.produto_pai_id: (i.produto_pai.descricao if i.produto_pai else str(i.produto_pai_id)) for i in oc.itens}
    for pai, numeros in sem_grupo.items():
        _add(
            "SEM_GRUPO_MOLDE",
            f"Produto {nomes[pai]} sem grupo de moldes vinculado.",
            numero_itens=numeros,
            produto_pai_id=str(pai),
        )
    for (pai, tamanho), numeros in sem_molde.items():
        _add(
            "SEM_MOLDE_TAMANHO",
            f"Grupo de moldes {grupos[pai].nome} sem molde do tamanho {tamanho}.",
            numero_itens=numeros,
            produto_pai_id=str(pai),
            tamanho=tamanho,
        )

    for (codigo, mensagem), dados in geo_problemas.items():
        _add(codigo, mensagem, bloqueia=dados["bloqueia"], numero_itens=sorted(dados["numero_itens"]))

    for t in oc.tecidos:
        if t.lote_id is None:
            nome = t.produto_pai.descricao if t.produto_pai else str(t.produto_pai_id)
            _add(
                "SEM_TECIDO",
                f"{nome} {t.cor or ''}".strip() + ": escolha o lote de tecido.",
                produto_pai_id=str(t.produto_pai_id),
                cor=t.cor,
            )

    # Aviso (não bloqueia): consumo planejado pelos encaixes atuais da OC
    # maior que o peso disponível do lote.
    for aviso in avisos_estoque(db, oc):
        _add(**aviso, bloqueia=False)
    return pendencias


def _consumo_por_lote(encaixes) -> dict[uuid.UUID, float]:
    """kg planejados por lote = Σ peso de uma camada × camadas. Encaixe
    multicor soma cada lote pelas linhas dele (Encaixe.consumo_por_lote)."""
    consumo: dict[uuid.UUID, float] = {}
    for e in encaixes:
        if e.status == "deletado":
            continue
        for lote_id, kg in e.consumo_por_lote().items():
            consumo[lote_id] = consumo.get(lote_id, 0.0) + kg
    return consumo


def reservas_kg(db: Session, excluir_oc_id: uuid.UUID | None = None) -> dict[uuid.UUID, float]:
    """kg reservados por lote — UMA consulta para todos os lotes.

    A reserva é o peso planejado (peso dos encaixes × camadas) de toda OC
    ENVIADA ou EM_CORTE que usa o lote: enquanto a OC não volta a rascunho,
    é concluída ou é cancelada, aquele peso não pode ser planejado por outra
    OC. RASCUNHO não reserva (pode mudar de lote à vontade) e CONCLUIDA não
    reserva (o peso já saiu do estoque, em consumo).

    `excluir_oc_id` tira a própria OC da conta — é o que permite comparar o
    plano da OC com o que sobra depois das outras.

    Duas somas: encaixes de um lote só (Encaixe.lote_id × peso × camadas) e
    encaixes multicor, que reservam cada lote pelas linhas de
    encaixe_camadas — o Encaixe.lote_id deles é só a cor principal e não
    pode entrar na primeira soma.
    """
    filtros = [
        Encaixe.status != "deletado",
        Encaixe.ordem_corte_id.is_not(None),
        OrdemCorte.status.in_(_RESERVANDO),
    ]
    if excluir_oc_id is not None:
        filtros.append(Encaixe.ordem_corte_id != excluir_oc_id)
    multicor = select(EncaixeCamada.encaixe_id)
    simples = (
        select(Encaixe.lote_id, func.sum(Encaixe.peso_kg * func.coalesce(Encaixe.num_camadas, 1)))
        .join(OrdemCorte, OrdemCorte.id == Encaixe.ordem_corte_id)
        .where(*filtros, Encaixe.lote_id.is_not(None), Encaixe.id.not_in(multicor))
        .group_by(Encaixe.lote_id)
    )
    por_cor = (
        select(EncaixeCamada.lote_id, func.sum(EncaixeCamada.peso_kg * EncaixeCamada.camadas))
        .join(Encaixe, Encaixe.id == EncaixeCamada.encaixe_id)
        .join(OrdemCorte, OrdemCorte.id == Encaixe.ordem_corte_id)
        .where(*filtros, EncaixeCamada.lote_id.is_not(None))
        .group_by(EncaixeCamada.lote_id)
    )
    reservas: dict[uuid.UUID, float] = {}
    for q in (simples, por_cor):
        for lote_id, total in db.execute(q).all():
            reservas[lote_id] = reservas.get(lote_id, 0.0) + float(total or 0.0)
    return reservas


def livre_kg(lote: LoteTecido, reservado: float = 0.0) -> float:
    """Quanto do lote dá para planejar agora: disponível menos o que as
    outras OCs já reservaram."""
    return round(float(lote.peso_disponivel_kg) - reservado, 3)


def avisos_estoque(db: Session, oc: OrdemCorte) -> list[dict]:
    """Planejado da OC × o que está LIVRE no lote (disponível menos a reserva
    das outras OCs). RASCUNHO não entra na própria reserva, então comparar
    com o livre de fora dá o mesmo número."""
    reservas = reservas_kg(db, excluir_oc_id=oc.id)
    lotes = {t.lote.id: t.lote for t in oc.tecidos if t.lote}
    avisos: list[dict] = []
    for lote_id, planejado in _consumo_por_lote(oc.encaixes).items():
        lote = lotes.get(lote_id) or db.get(LoteTecido, lote_id)
        disponivel = float(lote.peso_disponivel_kg) if lote else 0.0
        reservado = reservas.get(lote_id, 0.0)
        livre = round(disponivel - reservado, 3)
        if planejado > livre:
            codigo = lote.codigo_lote if lote else str(lote_id)
            avisos.append(
                {
                    "codigo": "ESTOQUE_INSUFICIENTE",
                    "mensagem": (
                        f"Lote {codigo}: planejado {planejado:.3f} kg, livre {livre:.3f} kg "
                        f"(disponível {disponivel:.3f} kg, reservado {reservado:.3f} kg por outras OCs)."
                    ),
                    "lote_id": str(lote_id),
                    "planejado_kg": round(planejado, 3),
                    "disponivel_kg": round(disponivel, 3),
                    "reservado_kg": round(reservado, 3),
                    "livre_kg": livre,
                }
            )
    return avisos


# ── Serialização ──────────────────────────────────────────────────────────────


def _lote_out(lote: LoteTecido | None) -> dict | None:
    if not lote:
        return None
    cor = lote.cor
    return {
        "id": str(lote.id),
        "codigo_lote": lote.codigo_lote,
        "modelo": cor.modelo.nome if cor and cor.modelo else None,
        "cor_tecido": cor.nome_cor if cor else None,
        "largura_util_cm": float(cor.largura_util_cm) if cor else None,
        "gramatura_g_m2": float(cor.gramatura_g_m2) if cor else None,
        "peso_disponivel_kg": float(lote.peso_disponivel_kg),
        "valor_kg": float(lote.valor_kg),
        "status": lote.status,
    }


def _resumo_out(db: Session, oc: OrdemCorte) -> dict:
    pedido = oc.pedido
    return {
        "id": str(oc.id),
        "numero": oc.numero,
        "numero_fmt": numero_fmt(oc.numero),
        "pedido_id": str(oc.pedido_id),
        "pedido_numero": pedido.numero if pedido else None,
        "pedido_status": pedido.status if pedido else None,
        "cliente": pedido.cliente_razao_social if pedido else None,
        "status": oc.status,
        "modo_camadas": oc.modo_camadas,
        "tipo_enfesto": oc.tipo_enfesto,
        "decisao_enfesto": oc.decisao_enfesto,
        "enfesto_avancado": enfesto_avancado(oc),
        "comprimento_max_cm": oc.comprimento_max_cm,
        "qualidade": oc.qualidade,
        "organizar_por": oc.organizar_por,
        "sugestao_mesa": oc.sugestao_mesa,
        "observacoes": oc.observacoes,
        "criado_em": oc.criado_em.isoformat() if oc.criado_em else None,
        "atualizado_em": oc.atualizado_em.isoformat() if oc.atualizado_em else None,
        "enviada_em": oc.enviada_em.isoformat() if oc.enviada_em else None,
        "iniciada_em": oc.iniciada_em.isoformat() if oc.iniciada_em else None,
        "concluida_em": oc.concluida_em.isoformat() if oc.concluida_em else None,
        "cortador": oc.cortador,
        "total_itens": len(oc.itens),
        "total_pecas": sum(i.quantidade for i in oc.itens),
        "desatualizada": desatualizada(db, oc),
        "encaixes_desatualizados": encaixes_desatualizados(oc),
    }


def ordem_out(db: Session, oc: OrdemCorte) -> dict:
    qtd_por_chave: dict[tuple, int] = {}
    for i in oc.itens:
        chave = (i.produto_pai_id, i.cor)
        qtd_por_chave[chave] = qtd_por_chave.get(chave, 0) + i.quantidade
    pendencias = conferir(db, oc)
    return {
        **_resumo_out(db, oc),
        "itens": [
            {
                "id": str(i.id),
                "item_pedido_id": str(i.item_pedido_id) if i.item_pedido_id else None,
                "numero_item": i.numero_item,
                "sku_id": i.sku_id,
                "sku_codigo": i.sku.codigo if i.sku else None,
                "produto_pai_id": str(i.produto_pai_id),
                "produto_codigo": i.produto_pai.codigo if i.produto_pai else None,
                "produto_descricao": i.produto_pai.descricao if i.produto_pai else None,
                "cor": i.cor,
                "tamanho": i.tamanho,
                "quantidade": i.quantidade,
                "grupo_molde_id": str(i.grupo_molde_id) if i.grupo_molde_id else None,
                "grupo_molde_nome": i.grupo_molde.nome if i.grupo_molde else None,
            }
            for i in oc.itens
        ],
        "tecidos": [
            {
                "id": str(t.id),
                "produto_pai_id": str(t.produto_pai_id),
                "produto_codigo": t.produto_pai.codigo if t.produto_pai else None,
                "produto_descricao": t.produto_pai.descricao if t.produto_pai else None,
                "cor": t.cor,
                "quantidade": qtd_por_chave.get((t.produto_pai_id, t.cor), 0),
                "lote_id": str(t.lote_id) if t.lote_id else None,
                "lote": _lote_out(t.lote),
            }
            for t in sorted(
                oc.tecidos, key=lambda t: (_norm(t.produto_pai.descricao if t.produto_pai else ""), _norm(t.cor))
            )
        ],
        "pendencias": pendencias,
        "pode_gerar_encaixes": oc.status == _EDITAVEL and not any(p["bloqueia"] for p in pendencias),
        "encaixes": [
            _encaixe_out(e) for e in sorted(oc.encaixes, key=lambda e: e.numero or 0) if e.status != "deletado"
        ],
    }


def _encaixe_out(e) -> dict:
    mapa = e.mapa_json or {}
    return {
        "id": str(e.id),
        "numero_enc": e.numero,
        "lote_id": str(e.lote_id) if e.lote_id else None,
        "tecido_nome": mapa.get("tecido_nome"),
        "enfesto": mapa.get("enfesto"),
        "parte": mapa.get("parte"),
        "parte_numero": mapa.get("parte_numero"),
        "total_partes": mapa.get("total_partes"),
        "comprimento_max_cm": mapa.get("comprimento_max_cm"),
        "num_camadas": e.num_camadas,
        "comp_metros": float(e.comp_metros) if e.comp_metros is not None else None,
        # peso_kg = uma camada; peso_total_kg = consumo do enfesto (× camadas)
        "peso_kg": float(e.peso_kg) if e.peso_kg is not None else None,
        "peso_total_kg": mapa.get("peso_total_kg"),
        "desperdicio_pct": float(e.desperdicio_pct) if e.desperdicio_pct is not None else None,
        "aproveitamento_pct": round(100.0 - float(e.desperdicio_pct), 2) if e.desperdicio_pct is not None else None,
        "pecas_por_tamanho": mapa.get("pecas_por_tamanho"),
        "pecas_parte": mapa.get("pecas_parte"),
        "sobra_total": mapa.get("sobra_total"),
        "motor_usado": mapa.get("motor_usado"),
        "qualidade": mapa.get("qualidade"),
        "tipo_enfesto": mapa.get("tipo_enfesto"),
        "modo_camadas": mapa.get("modo_camadas"),
        "grupo_corte": mapa.get("grupo_corte"),
        "produto_nome": mapa.get("produto_nome"),
        "risco": mapa.get("risco"),
        "camadas_por_cor": mapa.get("camadas_por_cor"),
        "status": e.status,
    }


# ── Decisão do enfesto ────────────────────────────────────────────────────────

_AUTOMATICO = "AUTOMATICO"


def enfesto_avancado(oc: OrdemCorte) -> dict:
    """Escolha manual do "Avançado": {tipo_enfesto, modo_camadas}, cada um
    AUTOMATICO (o sistema decide) ou o valor fixo."""
    escolha = oc.enfesto_avancado or {}
    return {
        "tipo_enfesto": escolha.get("tipo_enfesto") or _AUTOMATICO,
        "modo_camadas": escolha.get("modo_camadas") or _AUTOMATICO,
    }


def _unico(valores: list[str], padrao: str) -> str:
    """O valor comum a todos os lotes; divergindo, MISTO."""
    distintos = list(dict.fromkeys(v for v in valores if v))
    if not distintos:
        return padrao
    return distintos[0] if len(distintos) == 1 else "MISTO"


def _resumo_decisao(lotes: list[dict]) -> str:
    """Uma ou duas frases para o quadro "Decisão do sistema"."""
    if len(lotes) == 1:
        return lotes[0]["motivo"]
    return " ".join(f"{d.get('tecido') or 'Lote'}: {d['motivo']}" for d in lotes)


def _gravar_decisao(oc: OrdemCorte, decisoes: list[dict], lotes: dict) -> None:
    """Grava na OC o que a geração decidiu (tipo, modo e o porquê)."""
    for d in decisoes:
        # Multicor (plano por produto): todos os lotes do enfesto.
        codigos = [lotes.get(lid) for lid in d.get("lotes") or [d.get("lote_id")]]
        d["lote_codigo"] = " + ".join(c for c in codigos if c) or None
    oc.tipo_enfesto = _unico([d["tipo_enfesto"] for d in decisoes], "MESMA_FACE")
    modo = _unico([d["modo_camadas"] for d in decisoes], oc.modo_camadas)
    oc.modo_camadas = modo[:20]
    oc.decisao_enfesto = {"motivo": _resumo_decisao(decisoes), "lotes": decisoes} if decisoes else None


# ── Operações ─────────────────────────────────────────────────────────────────


def criar_ordem_corte(db: Session, pedido_id: uuid.UUID) -> dict:
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise ErroOC("Pedido não encontrado", 404)
    if pedido.status == "Cancelado":
        raise ErroOC("Pedido cancelado não gera Ordem de Corte.")
    ativa = oc_ativa_do_pedido(db, pedido_id)
    if ativa:
        raise ErroOC(f"Pedido já possui a Ordem de Corte ativa {numero_fmt(ativa.numero)}.", 409)
    itens = _itens_pedido(db, pedido_id)
    if not any(i.produto_id is not None for i in itens):
        raise ErroOC("O pedido não possui itens de produto para cortar.")

    ultimo = db.execute(select(func.max(OrdemCorte.numero))).scalar() or 0
    oc = OrdemCorte(numero=ultimo + 1, pedido_id=pedido_id, status=_EDITAVEL, modo_camadas="SEM_SOBRA")
    db.add(oc)
    # no_autoflush: o _snapshot consulta os grupos de molde, e num sessão com
    # autoflush ligado esse SELECT gravaria a OC antes de o pedido_hash (NOT
    # NULL) ser preenchido. O SessionLocal do app é autoflush=False, mas a
    # suíte não é — sem isto a criação quebra só no teste.
    with db.no_autoflush:
        _snapshot(db, oc, itens)
    try:
        db.commit()
    except IntegrityError:
        # Corrida com outra criação: ou a OC ativa do pedido (índice
        # parcial) ou o número — nos dois casos nada foi gravado.
        db.rollback()
        raise ErroOC("Outra Ordem de Corte foi criada ao mesmo tempo para este pedido; recarregue.", 409)
    return ordem_out(db, _carregar(db, oc.id))


def listar(db: Session, status: str | None = None, pedido_id: uuid.UUID | None = None) -> list[dict]:
    q = select(OrdemCorte).options(selectinload(OrdemCorte.pedido), selectinload(OrdemCorte.itens))
    if status:
        q = q.where(OrdemCorte.status == status.upper())
    if pedido_id:
        q = q.where(OrdemCorte.pedido_id == pedido_id)
    return [_resumo_out(db, oc) for oc in db.execute(q.order_by(OrdemCorte.numero.desc())).scalars().all()]


def lotes_disponiveis(db: Session, excluir_oc_id: uuid.UUID | None = None) -> list[dict]:
    """Lotes que podem ser escolhidos numa OC (lookup do assistente) — sem
    arquivados/esgotados, com modelo, cor, largura, gramatura e peso.

    Traz `peso_disponivel_kg`, `reservado_kg` (peso travado por outras OCs
    ENVIADA/EM_CORTE) e `livre_kg` (o que dá para planejar agora).
    `excluir_oc_id` deixa a própria OC de fora da reserva — use quando a
    tela for editar os tecidos de uma OC que já reservou.
    """
    lotes = (
        db.execute(
            select(LoteTecido)
            .where(LoteTecido.status.not_in(_LOTE_INDISPONIVEL))
            .options(selectinload(LoteTecido.cor).selectinload(CorTecido.modelo))
        )
        .scalars()
        .all()
    )
    reservas = reservas_kg(db, excluir_oc_id=excluir_oc_id)
    saida = []
    for lt in lotes:
        item = _lote_out(lt)
        reservado = round(reservas.get(lt.id, 0.0), 3)
        item["reservado_kg"] = reservado
        item["livre_kg"] = livre_kg(lt, reservado)
        saida.append(item)
    saida.sort(key=lambda lt: (_norm(lt["modelo"]), _norm(lt["cor_tecido"]), lt["codigo_lote"]))
    return saida


def obter(db: Session, oc_id: uuid.UUID) -> dict | None:
    oc = _carregar(db, oc_id)
    return ordem_out(db, oc) if oc else None


def obter_do_pedido(db: Session, pedido_id: uuid.UUID) -> dict | None:
    ativa = oc_ativa_do_pedido(db, pedido_id)
    return obter(db, ativa.id) if ativa else None


def definir_tecidos(db: Session, oc_id: uuid.UUID, escolhas: list[dict]) -> dict:
    """escolhas: [{produto_pai_id, cor, lote_id|None}] — lote_id None limpa."""
    oc = _obter_editavel(db, oc_id)
    linhas = {(t.produto_pai_id, _norm(t.cor)): t for t in oc.tecidos}
    for e in escolhas:
        linha = linhas.get((e["produto_pai_id"], _norm(e.get("cor"))))
        if not linha:
            raise ErroOC(f"Produto/cor não pertence à Ordem de Corte: {e['produto_pai_id']} / {e.get('cor')}")
        lote_id = e.get("lote_id")
        if lote_id is not None:
            lote = db.get(LoteTecido, lote_id)
            if not lote:
                raise ErroOC(f"Lote de tecido não encontrado: {lote_id}", 404)
            if lote.status in _LOTE_INDISPONIVEL:
                raise ErroOC(f"Lote {lote.codigo_lote} está {lote.status} e não pode ser usado.")
        linha.lote_id = lote_id
    db.commit()
    db.expire_all()
    return ordem_out(db, _carregar(db, oc_id))


def atualizar(db: Session, oc_id: uuid.UUID, dados: dict) -> dict:
    """dados: enfesto_tipo / enfesto_modo (escolha manual do "Avançado":
    AUTOMATICO ou valor fixo), comprimento_max_cm, qualidade e
    organizar_por (só em RASCUNHO) e/ou observacoes. Mudar o limite deixa os
    encaixes atuais desatualizados (encaixes_desatualizados) até regerar;
    enfesto, qualidade e organizar_por só valem para a próxima geração."""
    oc = _carregar(db, oc_id)
    if not oc:
        raise ErroOC("Ordem de Corte não encontrada", 404)
    if oc.status in _FINAIS:
        raise ErroOC(f"Ordem de Corte {oc.status} não pode ser alterada.", 409)
    avancado = enfesto_avancado(oc)
    novo = {
        "tipo_enfesto": dados.get("enfesto_tipo") or avancado["tipo_enfesto"],
        "modo_camadas": dados.get("enfesto_modo") or avancado["modo_camadas"],
    }
    if novo != avancado:
        if novo["tipo_enfesto"] not in (_AUTOMATICO, *TIPOS_ENFESTO):
            raise ErroOC(f"Tipo de enfesto inválido: {novo['tipo_enfesto']}")
        if novo["modo_camadas"] not in (_AUTOMATICO, *MODOS_CAMADAS):
            raise ErroOC(f"Modo de camadas inválido: {novo['modo_camadas']}")
        if oc.status != _EDITAVEL:
            raise ErroOC("O enfesto só pode ser alterado em RASCUNHO.", 409)
        automatico = all(v == _AUTOMATICO for v in novo.values())
        oc.enfesto_avancado = None if automatico else novo
    if dados.get("comprimento_max_cm") is not None and dados["comprimento_max_cm"] != oc.comprimento_max_cm:
        limite = dados["comprimento_max_cm"]
        if not isinstance(limite, int) or not COMPRIMENTO_MAX_MIN_CM <= limite <= COMPRIMENTO_MAX_MAX_CM:
            raise ErroOC(f"Comprimento máximo deve estar entre {COMPRIMENTO_MAX_MIN_CM} e {COMPRIMENTO_MAX_MAX_CM} cm.")
        if oc.status != _EDITAVEL:
            raise ErroOC("Comprimento máximo só pode ser alterado em RASCUNHO.", 409)
        oc.comprimento_max_cm = limite
        for e in oc.encaixes:
            if e.status != "deletado":
                # dict novo: a coluna JSON não rastreia mutação in-place.
                e.mapa_json = {**(e.mapa_json or {}), _MARCA_LIMITE: True}
    if dados.get("qualidade") is not None and dados["qualidade"] != oc.qualidade:
        if dados["qualidade"] not in QUALIDADES:
            raise ErroOC(f"Qualidade inválida: {dados['qualidade']}")
        if oc.status != _EDITAVEL:
            raise ErroOC("Qualidade do encaixe só pode ser alterada em RASCUNHO.", 409)
        oc.qualidade = dados["qualidade"]
    if dados.get("organizar_por") is not None and dados["organizar_por"] != oc.organizar_por:
        if dados["organizar_por"] not in ORGANIZAR_POR:
            raise ErroOC(f"Organização inválida: {dados['organizar_por']}")
        if oc.status != _EDITAVEL:
            raise ErroOC("A organização do corte só pode ser alterada em RASCUNHO.", 409)
        oc.organizar_por = dados["organizar_por"]
    if "observacoes" in dados:
        oc.observacoes = dados["observacoes"] or None
    db.commit()
    db.expire_all()
    return ordem_out(db, _carregar(db, oc_id))


def atualizar_do_pedido(db: Session, oc_id: uuid.UUID) -> dict:
    """Refaz o snapshot dos itens (só em RASCUNHO), mantendo os lotes já
    escolhidos para (produto, cor) que continuam no pedido."""
    oc = _obter_editavel(db, oc_id)
    itens = _itens_pedido(db, oc.pedido_id)
    if not any(i.produto_id is not None for i in itens):
        raise ErroOC("O pedido não possui mais itens de produto para cortar.")
    _snapshot(db, oc, itens)
    db.commit()
    db.expire_all()
    return ordem_out(db, _carregar(db, oc_id))


def cancelar(db: Session, oc_id: uuid.UUID) -> dict:
    """RASCUNHO/ENVIADA/EM_CORTE → CANCELADA. Cancelar em EM_CORTE não dá
    baixa nenhuma: consumo só existe depois de CONCLUIDA, e aí cancelar já
    está bloqueado (_FINAIS)."""
    oc = _carregar(db, oc_id)
    if not oc:
        raise ErroOC("Ordem de Corte não encontrada", 404)
    if oc.status in _FINAIS:
        raise ErroOC(f"Ordem de Corte já está {oc.status}.", 409)
    oc.status = "CANCELADA"
    db.commit()
    db.expire_all()
    return ordem_out(db, _carregar(db, oc_id))


def enviar_a_producao(db: Session, oc_id: uuid.UUID) -> dict:
    """RASCUNHO → ENVIADA: exige encaixes gerados e OC em dia com o pedido.
    Depois disso tecidos, modo e encaixes ficam travados (só RASCUNHO edita).
    A partir daqui o lote fica reservado (ver reservas_kg)."""
    oc = _carregar(db, oc_id)
    if not oc:
        raise ErroOC("Ordem de Corte não encontrada", 404)
    if oc.status != "RASCUNHO":
        raise ErroOC(f"Ordem de Corte em {oc.status} não pode ser enviada (só em RASCUNHO).", 409)
    if not any(e.status != "deletado" for e in oc.encaixes):
        raise ErroOC("Gere os encaixes antes de enviar à produção.", 409)
    if desatualizada(db, oc):
        raise ErroOC("O pedido mudou depois da Ordem de Corte. Atualize do pedido e regere os encaixes.", 409)
    if encaixes_desatualizados(oc):
        raise ErroOC(
            f"Os encaixes não foram gerados com o comprimento máximo atual ({oc.comprimento_max_cm} cm). "
            "Regere os encaixes antes de enviar.",
            409,
        )
    oc.status = "ENVIADA"
    oc.enviada_em = _agora()
    db.commit()
    db.expire_all()
    return ordem_out(db, _carregar(db, oc_id))


# ── Produção (OC6a) ───────────────────────────────────────────────────────────


def voltar_rascunho(db: Session, oc_id: uuid.UUID) -> dict:
    """ENVIADA → RASCUNHO: libera a reserva do lote. Só enquanto não começou
    a cortar — depois de EM_CORTE o corte já mexeu no plano."""
    oc = _carregar(db, oc_id)
    if not oc:
        raise ErroOC("Ordem de Corte não encontrada", 404)
    if oc.status != "ENVIADA":
        raise ErroOC(f"Só uma Ordem de Corte ENVIADA volta para rascunho (esta está {oc.status}).", 409)
    if oc.iniciada_em is not None:
        raise ErroOC("A Ordem de Corte já iniciou o corte e não volta para rascunho.", 409)
    oc.status = "RASCUNHO"
    oc.enviada_em = None
    oc.cortador = None
    db.commit()
    db.expire_all()
    return ordem_out(db, _carregar(db, oc_id))


def iniciar_corte(db: Session, oc_id: uuid.UUID, cortador: str | None = None) -> dict:
    """ENVIADA → EM_CORTE: o corte começa. A reserva continua valendo."""
    oc = _carregar(db, oc_id)
    if not oc:
        raise ErroOC("Ordem de Corte não encontrada", 404)
    if oc.status != "ENVIADA":
        raise ErroOC(
            f"Só uma Ordem de Corte ENVIADA inicia o corte (esta está {oc.status}).",
            409,
        )
    oc.status = "EM_CORTE"
    oc.iniciada_em = _agora()
    if cortador:
        oc.cortador = cortador
    db.commit()
    db.expire_all()
    return ordem_out(db, _carregar(db, oc_id))


def concluir(db: Session, oc_id: uuid.UUID, cortador: str, consumos: list[dict], observacao: str | None = None) -> dict:
    """EM_CORTE → CONCLUIDA: baixa o peso real de cada lote e grava o consumo.

    Uma transação só: consumo + status da OC + status dos lotes entram ou
    saem juntos. Por isso usa `lote_service.debitar` (que não commita) em
    vez de `lote_service.consumir` (que commita).

    `consumos`: [{lote_id, kg_real?, sobra_kg?}] — kg_real padrão é o
    planejado da OC para o lote; sobra_kg é o retalho medido (só registro).
    Lote não listado usa o planejado. Lote listado que não é da OC → 404.
    """
    oc = _carregar(db, oc_id)
    if not oc:
        raise ErroOC("Ordem de Corte não encontrada", 404)
    if oc.status != "EM_CORTE":
        raise ErroOC(f"Só uma Ordem de Corte EM_CORTE pode ser concluída (esta está {oc.status}).", 409)

    planejado = _consumo_por_lote(oc.encaixes)
    if not planejado:
        raise ErroOC("A Ordem de Corte não tem consumo planejado para concluir.", 409)

    lotes_oc = {t.lote.id: t.lote for t in oc.tecidos if t.lote}
    pedidos: dict[uuid.UUID, dict] = {}
    for item in consumos or []:
        lote_id = uuid.UUID(str(item["lote_id"]))
        if lote_id in pedidos:
            raise ErroOC(f"Lote repetido no consumo: {lote_id}.", 400)
        if lote_id not in lotes_oc and lote_id not in planejado:
            raise ErroOC(f"Lote não pertence à Ordem de Corte: {lote_id}.", 404)
        pedidos[lote_id] = item
    # Lote planejado e não informado consome o planejado.
    for lote_id in planejado:
        pedidos.setdefault(lote_id, {"lote_id": lote_id, "kg_real": planejado[lote_id], "sobra_kg": None})

    agora = _agora()
    for lote_id, item in pedidos.items():
        lote = lotes_oc.get(lote_id) or db.get(LoteTecido, lote_id)
        if not lote:
            raise ErroOC(f"Lote de tecido não encontrado: {lote_id}.", 404)
        kg_real = item.get("kg_real")
        kg = float(kg_real) if kg_real is not None else float(planejado.get(lote_id, 0.0))
        if kg < 0:
            raise ErroOC(f"Peso negativo no consumo do lote {lote.codigo_lote}.", 400)
        sobra = item.get("sobra_kg")
        if sobra is not None and float(sobra) < 0:
            raise ErroOC(f"Sobra negativa no consumo do lote {lote.codigo_lote}.", 400)
        db.add(
            ConsumoLote(
                lote_id=lote.id,
                ordem_corte_id=oc.id,
                pedido_id=oc.pedido_id,
                tipo="CONSUMO",
                peso_consumido_kg=round(kg, 3),
                peso_planejado_kg=round(float(planejado.get(lote_id, kg)), 3),
                peso_retalho_kg=round(float(sobra), 3) if sobra is not None else None,
                data_consumo=agora,
                observacao=(observacao or "").strip() or None,
            )
        )
        lote_service.debitar(lote, kg)

    oc.status = "CONCLUIDA"
    oc.concluida_em = agora
    if cortador:
        oc.cortador = cortador
    db.commit()
    db.expire_all()
    return ordem_out(db, _carregar(db, oc_id))


def reabrir(db: Session, oc_id: uuid.UUID, quem: str, observacao: str | None = None) -> dict:
    """CONCLUIDA → EM_CORTE: estorna o consumo da OC e devolve o peso.

    Estorna só os consumos que ainda não foram estornados (cada ESTORNO
    aponta para o CONSUMO que desfaz), então concluir/reabrir em ciclo
    funciona: a segunda reabertura devolve o peso da segunda conclusão.
    """
    oc = _carregar(db, oc_id)
    if not oc:
        raise ErroOC("Ordem de Corte não encontrada", 404)
    if oc.status != "CONCLUIDA":
        raise ErroOC(f"Só uma Ordem de Corte CONCLUIDA pode ser reaberta (esta está {oc.status}).", 409)

    estornados = set(
        db.execute(select(ConsumoLote.estorno_de_id).where(ConsumoLote.ordem_corte_id == oc.id)).scalars().all()
    )
    pendentes = (
        db.execute(
            select(ConsumoLote)
            .where(ConsumoLote.ordem_corte_id == oc.id, ConsumoLote.tipo == "CONSUMO")
            .order_by(ConsumoLote.data_consumo, ConsumoLote.id)
        )
        .scalars()
        .all()
    )
    vivos = [c for c in pendentes if c.id not in estornados]
    if not vivos:
        raise ErroOC("A Ordem de Corte não tem consumo para estornar.", 409)

    agora = _agora()
    assinatura = (observacao or "").strip()
    nota = f"Reabertura por {quem} em {agora:%d/%m/%Y %H:%M}".strip()
    if assinatura:
        nota = f"{nota} — {assinatura}"
    for cons in vivos:
        kg = float(cons.peso_consumido_kg or 0.0)
        if cons.lote_id:
            lote = db.get(LoteTecido, cons.lote_id)
            if lote:
                lote_service.creditar(lote, kg)
        db.add(
            ConsumoLote(
                lote_id=cons.lote_id,
                ordem_corte_id=oc.id,
                pedido_id=cons.pedido_id,
                tipo="ESTORNO",
                estorno_de_id=cons.id,
                peso_consumido_kg=round(kg, 3),
                peso_planejado_kg=cons.peso_planejado_kg,
                peso_retalho_kg=cons.peso_retalho_kg,
                data_consumo=agora,
                observacao=nota,
            )
        )
    oc.status = "EM_CORTE"
    oc.concluida_em = None
    db.commit()
    db.expire_all()
    return ordem_out(db, _carregar(db, oc_id))


# ── Encaixes da OC ────────────────────────────────────────────────────────────


def montar_pares_oc(db: Session, oc: OrdemCorte) -> tuple[list, list[str]]:
    """Entrada neutra do nesting a partir da OC: para cada item, os moldes
    do tamanho (uma entrada por parte) com o lote escolhido para
    (produto, cor). Item que não entra vira aviso — nunca some calado."""
    grupos = _grupos_por_produto(db, {i.produto_pai_id for i in oc.itens})
    lotes = {(t.produto_pai_id, _norm(t.cor)): t.lote for t in oc.tecidos}
    entradas: list = []
    avisos: list[str] = []
    for item in oc.itens:
        rotulo = f"Item {item.numero_item:03d} ({item.cor or ''} {item.tamanho or ''})".replace("  ", " ")
        if item.quantidade <= 0:
            avisos.append(f"{rotulo}: quantidade zero — ignorado.")
            continue
        lote = lotes.get((item.produto_pai_id, _norm(item.cor)))
        if not lote:
            avisos.append(f"{rotulo}: sem lote de tecido — ignorado.")
            continue
        moldes = moldes_do_tamanho(grupos.get(item.produto_pai_id), item.tamanho)
        if not moldes:
            avisos.append(f"{rotulo}: sem molde do tamanho — ignorado.")
            continue
        entradas.extend((lote, molde, item.quantidade) for molde in moldes)
    return entradas, avisos


def validar_geracao(db: Session, oc_id: uuid.UUID) -> OrdemCorte:
    """Regras para gerar encaixes — o router chama antes de enfileirar o job
    (erro volta na hora, sem 202) e gerar_encaixes de novo ao rodar (a OC pode
    ter mudado enquanto o job esperava na fila)."""
    oc = _obter_editavel(db, oc_id)
    if desatualizada(db, oc):
        raise ErroOC("O pedido mudou depois da Ordem de Corte. Use 'Atualizar do pedido' antes de gerar.", 409)
    bloqueios = [p["mensagem"] for p in conferir(db, oc) if p["bloqueia"]]
    if bloqueios:
        raise ErroOC("Resolva as pendências antes de gerar: " + " | ".join(bloqueios), 409)
    return oc


def gerar_encaixes(db: Session, oc_id: uuid.UUID, *, progresso: nesting_service.Progresso | None = None) -> dict:
    """Gera (ou regera) os encaixes da OC com o motor v2 e a qualidade da OC.
    Os anteriores viram 'deletado' e os novos são gravados na MESMA transação,
    só depois do motor terminar — falha ou cancelamento (GeracaoCancelada,
    vinda de `progresso`) não mexem em nada. Roda em segundo plano
    (nesting_jobs); `progresso` é o do job.

    Depois de gravar, se o limite da OC é menor que a maior mesa da fábrica,
    simula a mesa maior (v2 RAPIDO, sem gravar) e deixa a sugestão na OC
    quando a economia passa de alerta_economia_pct (_sugerir_mesa)."""
    cfg = nesting_service.config_producao(db)
    oc = validar_geracao(db, oc_id)

    entradas, avisos = montar_pares_oc(db, oc)

    lotes_codigo = {str(t.lote.id): t.lote.codigo_lote for t in oc.tecidos if t.lote}

    def _substituir_anteriores(decisoes: list[dict]) -> None:
        for e in oc.encaixes:
            if e.status != "deletado":
                e.status = "deletado"
        oc.sugestao_mesa = None
        _gravar_decisao(oc, decisoes, lotes_codigo)

    pedido = oc.pedido
    avancado = enfesto_avancado(oc)
    limite, qualidade = oc.comprimento_max_cm, oc.qualidade
    try:
        resultado = nesting_service.gerar_de_entradas(
            db,
            pedido,
            entradas,
            modo=avancado["modo_camadas"],
            tipo_enfesto=avancado["tipo_enfesto"],
            ordem_corte_id=oc.id,
            descricao=f"{numero_fmt(oc.numero)} · Pedido {pedido.numero}",
            comprimento_max_cm=limite,
            qualidade=qualidade,
            progresso=progresso,
            antes_de_gravar=_substituir_anteriores,
            tempo_maximo_s=cfg["tempo_maximo_oc_s"],
            organizar_por=oc.organizar_por,
            tolerancia_pct=cfg["tolerancia_tecido_pct"],
        )
    except ValueError as exc:
        raise ErroOC(str(exc))
    except nesting_service.ErroNesting as exc:
        # Depois das duas tentativas (retry automático) — mensagem legível.
        raise ErroOC(str(exc), 500)

    db.expire_all()
    oc = _carregar(db, oc_id)
    lotes = {t.lote.id: t.lote.codigo_lote for t in oc.tecidos if t.lote}

    # Totais por tamanho somando cada enfesto uma vez (o pecas_por_tamanho do
    # enfesto só vem na parte 1 — o que cada parte corta de fato está em
    # pecas_parte).
    por_tamanho: dict[tuple, dict] = {}
    vistos: set[tuple] = set()
    for enc in resultado["encaixes"]:
        enc["lote_codigo"] = lotes.get(uuid.UUID(enc["lote_id"])) if enc["lote_id"] else None
        chave_enfesto = (enc.get("grupo_corte") or enc["lote_id"], enc["enfesto"])
        if chave_enfesto in vistos or not enc["pecas_por_tamanho"]:
            continue
        vistos.add(chave_enfesto)
        for linha in enc["pecas_por_tamanho"]:
            k = (linha.get("grupo_nome"), linha.get("tamanho"))
            acc = por_tamanho.setdefault(k, {"grupo_nome": k[0], "tamanho": k[1], "pecas": 0, "sobra": 0})
            acc["pecas"] += linha["pecas"]
            acc["sobra"] += linha["sobra"]

    avisos_out = [{"codigo": "AVISO", "mensagem": m} for m in avisos + resultado["avisos"]] + avisos_estoque(db, oc)

    escolhas = {d["grupo"]: (d["tipo_enfesto"], d["modo_camadas"]) for d in resultado["decisoes"]}
    sugestao = None
    if limite < cfg["comprimento_max_mesa_cm"]:
        sugestao = _sugerir_mesa(db, oc, entradas, escolhas, resultado["totais"], cfg, progresso)

    return {
        "ordem_corte_id": str(oc.id),
        "modo_camadas": oc.modo_camadas,
        "tipo_enfesto": oc.tipo_enfesto,
        "decisao_enfesto": oc.decisao_enfesto,
        "comprimento_max_cm": limite,
        "qualidade": qualidade,
        "motor_usado": resultado["motor_usado"],
        "encaixes": resultado["encaixes"],
        "avisos": avisos_out,
        "pecas_por_tamanho": list(por_tamanho.values()),
        "sobra_total": sum(p["sobra_total"] for p in resultado["planos"].values()),
        "totais": resultado["totais"],
        "sugestao_mesa": sugestao,
    }


# Teto duro da simulação de mesa maior (o tempo_max_s do RAPIDO é brando).
SIMULACAO_MAX_S = 300.0


def _sugerir_mesa(
    db: Session,
    oc: OrdemCorte,
    entradas: list,
    escolhas: dict[str, tuple[str, str]],
    atual: dict,
    cfg: dict,
    progresso: nesting_service.Progresso | None,
) -> dict | None:
    """Simula a OC na maior mesa da fábrica (v2 RAPIDO, sem gravar encaixes,
    com o mesmo enfesto decidido na geração — `escolhas`) e grava
    oc.sugestao_mesa se a economia em metros (todas as camadas) for
    >= alerta_economia_pct. Falha, tempo excedido ou cancelamento: só log —
    os encaixes já estão gravados e a sugestão é opcional."""
    mesa = cfg["comprimento_max_mesa_cm"]
    inicio = time.monotonic()

    def _progresso(**estado) -> None:
        if time.monotonic() - inicio > SIMULACAO_MAX_S:
            raise TimeoutError(f"simulação passou de {SIMULACAO_MAX_S:g} s")
        if progresso is not None:
            progresso(**{**estado, "fase": f"Simulando mesa de {mesa} cm · {estado.get('fase', '')}"})

    try:
        sugerido = nesting_service.simular_totais(
            entradas,
            escolhas=escolhas,
            comprimento_max_cm=mesa,
            qualidade="RAPIDO",
            progresso=_progresso,
            organizar_por=oc.organizar_por,
            tolerancia_pct=cfg["tolerancia_tecido_pct"],
        )
    except Exception as exc:  # inclui GeracaoCancelada: o resultado já foi gravado
        logger.warning("[OC] %s: simulação da mesa de %s cm ignorada: %s", numero_fmt(oc.numero), mesa, exc)
        return None

    metros = atual["metros"]
    economia_m = round(metros - sugerido["metros"], 3)
    economia_pct = round(economia_m / metros * 100, 2) if metros > 0 else 0.0
    logger.info(
        "[OC] %s: mesa de %s cm → %.3f m (atual %.3f m, economia %.2f%%)",
        numero_fmt(oc.numero),
        mesa,
        sugerido["metros"],
        metros,
        economia_pct,
    )
    if economia_pct < cfg["alerta_economia_pct"]:
        return None
    sugestao = {
        "limite_cm": mesa,
        "metros_atual": metros,
        "metros_sugerido": sugerido["metros"],
        "enfestos_atual": atual["mesas"],
        "enfestos_sugerido": sugerido["mesas"],
        "economia_m": economia_m,
        "economia_pct": economia_pct,
        "economia_kg": round(atual["peso_kg"] - sugerido["peso_kg"], 3),
        "economia_rs": round(atual["custo"] - sugerido["custo"], 2),
    }
    oc.sugestao_mesa = sugestao
    db.commit()
    return sugestao


def aplicar_sugestao_mesa(db: Session, oc_id: uuid.UUID) -> dict:
    """Passa o comprimento máximo da OC para o da sugestão (os encaixes
    atuais ficam desatualizados) — o router dispara a nova geração."""
    oc = _obter_editavel(db, oc_id)
    if not oc.sugestao_mesa:
        raise ErroOC("A Ordem de Corte não tem sugestão de mesa.", 404)
    limite = int(oc.sugestao_mesa["limite_cm"])
    oc.sugestao_mesa = None
    return atualizar(db, oc_id, {"comprimento_max_cm": limite})


def descartar_sugestao_mesa(db: Session, oc_id: uuid.UUID) -> dict:
    """Some com a sugestão — ela só volta se uma nova geração a recalcular."""
    oc = _obter_editavel(db, oc_id)
    oc.sugestao_mesa = None
    db.commit()
    db.expire_all()
    return ordem_out(db, _carregar(db, oc_id))


# ModeloTecido.max_camadas tem default 15 — usado na simulação de linhas
# ainda sem lote escolhido (sem lote não há modelo de tecido).
_MAX_CAMADAS_PADRAO = 15


def simular(db: Session, oc_id: uuid.UUID, modo: str | None = None) -> dict:
    """Só o plano de enfesto (sem nesting) de cada lote, para a tela
    comparar os modos. Linhas sem lote são simuladas por (produto, cor)
    com o máximo de camadas padrão (max_camadas_estimado=True). Com a OC
    organizada por PRODUTO, cada produto do lote é um grupo à parte (como na
    geração)."""
    oc = _carregar(db, oc_id)
    if not oc:
        raise ErroOC("Ordem de Corte não encontrada", 404)
    modo = (modo or oc.modo_camadas).upper()
    if modo not in MODOS_CAMADAS:
        raise ErroOC(f"Modo de camadas inválido: {modo}")

    linhas = {(t.produto_pai_id, _norm(t.cor)): t for t in oc.tecidos}
    grupos: dict = {}
    for item in oc.itens:
        if item.quantidade <= 0 or not _norm(item.tamanho):
            continue
        tecido = linhas.get((item.produto_pai_id, _norm(item.cor)))
        lote = tecido.lote if tecido else None
        if not lote:
            gkey = ("SEM_LOTE", item.produto_pai_id, _norm(item.cor))
        elif oc.organizar_por == "PRODUTO":
            gkey = f"{lote.id}:{item.produto_pai_id}"
        else:
            gkey = lote.id
        g = grupos.setdefault(gkey, {"chave": gkey, "lote": lote, "qtds": {}, "rotulos": {}, "produtos_cores": []})
        produto = item.produto_pai.descricao if item.produto_pai else str(item.produto_pai_id)
        k = (item.produto_pai_id, _norm(item.tamanho))
        g["qtds"][k] = g["qtds"].get(k, 0) + item.quantidade
        g["rotulos"][k] = {"produto": produto, "tamanho": item.tamanho.strip()}
        pc = f"{produto} {item.cor or ''}".strip()
        if pc not in g["produtos_cores"]:
            g["produtos_cores"].append(pc)

    saida = []
    for g in grupos.values():
        lote = g["lote"]
        cor = lote.cor if lote else None
        max_camadas = cor.modelo.max_camadas if cor and cor.modelo else _MAX_CAMADAS_PADRAO
        plano = planejar(g["qtds"], max_camadas, modo)
        saida.append(
            {
                "lote_id": str(lote.id) if lote else None,
                # Chave do grupo (igual ao lote_id quando a OC é por cor).
                "grupo": g["chave"] if isinstance(g["chave"], str) else (str(lote.id) if lote else None),
                "lote_codigo": lote.codigo_lote if lote else None,
                "tecido": f"{cor.modelo.nome} — {cor.nome_cor}" if cor and cor.modelo else None,
                "produtos_cores": g["produtos_cores"],
                "max_camadas": max_camadas,
                "max_camadas_estimado": lote is None,
                "enfestos": [
                    {"camadas": e["camadas"], "tamanhos": linhas_enfesto(e, g["rotulos"])} for e in plano["enfestos"]
                ],
                "total_enfestos": len(plano["enfestos"]),
                "total_camadas": sum(e["camadas"] for e in plano["enfestos"]),
                "tamanhos": linhas_enfesto(plano, g["rotulos"]),
                "sobra_total": plano["sobra_total"],
            }
        )
    return {
        "modo": modo,
        "grupos": saida,
        "total_enfestos": sum(g["total_enfestos"] for g in saida),
        "sobra_total": sum(g["sobra_total"] for g in saida),
    }
