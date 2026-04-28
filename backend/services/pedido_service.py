import uuid
from datetime import date

from sqlalchemy.orm import Session, selectinload

from models.molde import Molde
from models.pedido import Pedido, PedidoPeca, PedidoTecido
from models.tecido import CorTecido, LoteTecido, ModeloTecido
from schemas.pedido_schema import (
    AdicionarGrupoPecaCreate,
    PedidoCreate,
    PedidoStatusUpdate,
    PedidoTecidoCreate,
    PedidoUpdate,
)
from services.gramatura_service import (
    aplicar_encolhimento,
    calcular_custo,
    metros_para_peso,
)

_MULT = {"simples": 1, "par": 2, "par_sem_espelho": 2}
_STATUS_VALIDOS = {"rascunho", "processando", "concluido", "cancelado"}


def _opts_full():
    return [
        selectinload(Pedido.pedido_tecidos).selectinload(PedidoTecido.tecido),
        selectinload(Pedido.pedido_tecidos)
            .selectinload(PedidoTecido.lote)
            .selectinload(LoteTecido.cor)
            .selectinload(CorTecido.modelo),
        selectinload(Pedido.pecas).selectinload(PedidoPeca.molde).selectinload(Molde.grupo),
        selectinload(Pedido.pecas).selectinload(PedidoPeca.tecido),
        selectinload(Pedido.pecas).selectinload(PedidoPeca.cor_tecido)
            .selectinload(CorTecido.modelo),
    ]


# ── Listagem ──────────────────────────────────────────────────────────

def listar(db: Session) -> list[dict]:
    pedidos = (
        db.query(Pedido)
        .options(selectinload(Pedido.pecas).selectinload(PedidoPeca.molde))
        .filter(Pedido.status != "cancelado")
        .order_by(Pedido.criado_em.desc())
        .all()
    )
    return [_to_list_dict(p) for p in pedidos]


def _to_list_dict(p: Pedido) -> dict:
    grupos = {str(pp.molde.grupo_id) for pp in p.pecas if pp.molde.grupo_id}
    return {
        "id": str(p.id),
        "num_pedido": p.num_pedido,
        "data_pedido": p.data_pedido.isoformat(),
        "cliente": p.cliente,
        "status": p.status,
        "total_grupos": len(grupos),
        "criado_em": p.criado_em.isoformat(),
    }


# ── Próximo número sequencial ─────────────────────────────────────────

def proximo_numero(db: Session) -> str:
    numeros = [row[0] for row in db.query(Pedido.num_pedido).all()]
    max_val = 0
    for num in numeros:
        try:
            n = int(num.strip())
            if n > max_val:
                max_val = n
        except (ValueError, AttributeError):
            pass
    return str(max_val + 1).zfill(3)


# ── Detalhe ───────────────────────────────────────────────────────────

def obter_detalhe(db: Session, pedido_id: uuid.UUID) -> dict | None:
    pedido = (
        db.query(Pedido)
        .options(*_opts_full())
        .filter(Pedido.id == pedido_id)
        .first()
    )
    if not pedido:
        return None
    return _to_detalhe_dict(pedido)


def _to_detalhe_dict(pedido: Pedido) -> dict:
    # Mapa cor_id → codigo_lote (para exibição na coluna TECIDO)
    cor_to_codigo_lote: dict[str, str] = {}
    for pt in pedido.pedido_tecidos:
        if pt.lote and pt.lote.cor:
            cid = str(pt.lote.cor.id)
            if cid not in cor_to_codigo_lote:
                cor_to_codigo_lote[cid] = pt.lote.codigo_lote

    # Agrupa pedido_pecas por (grupo_id, tamanho)
    grupos_dict: dict[tuple, dict] = {}
    for pp in pedido.pecas:
        m = pp.molde
        if not m.grupo_id:
            continue
        key = (str(m.grupo_id), m.tamanho or "")
        if key not in grupos_dict:
            cor_tecido = pp.cor_tecido
            tecido = pp.tecido
            cor_id_str = str(pp.cor_id) if pp.cor_id else None

            if cor_tecido:
                codigo_lote = cor_to_codigo_lote.get(cor_id_str or "", "")
                nome_display = f"{cor_tecido.modelo.nome} — {cor_tecido.nome_cor}"
                if codigo_lote:
                    nome_display += f" ({codigo_lote})"
                tecido_nome = nome_display
                tecido_id = f"cor:{cor_id_str}"
            else:
                tecido_nome = tecido.nome if tecido else None
                tecido_id = str(pp.tecido_id) if pp.tecido_id else None

            grupos_dict[key] = {
                "grupo_id": str(m.grupo_id),
                "grupo_nome": m.grupo.nome if m.grupo else "—",
                "tamanho": m.tamanho or "—",
                "quantidade": pp.quantidade,
                "tecido_id": tecido_id,
                "tecido_nome": tecido_nome,
                "cor_id": cor_id_str,
            }

    ordem_tamanho = {"PP": 0, "P": 1, "M": 2, "G": 3, "GG": 4, "XGG": 5}
    grupos_pecas = sorted(
        grupos_dict.values(),
        key=lambda g: (g["grupo_nome"], ordem_tamanho.get(g["tamanho"], 99)),
    )

    tecidos = []
    for pt in pedido.pedido_tecidos:
        if pt.lote:
            cor = pt.lote.cor
            modelo = cor.modelo
            tecidos.append({
                "pt_id": str(pt.id),
                "id": str(pt.lote.id),
                "nome": f"{modelo.nome} — {cor.nome_cor}",
                "lote_id": str(pt.lote.id),
                "codigo_lote": pt.lote.codigo_lote,
                "largura_util_cm": float(cor.largura_util_cm),
                "gramatura_g_m2": float(cor.gramatura_g_m2),
                "valor_por_kg": float(pt.lote.valor_kg),
                "encolhimento_pct": float(cor.encolhimento_pct),
                "peso_disponivel_kg": float(pt.lote.peso_disponivel_kg),
                "cor_id": str(cor.id),
                "modelo_nome": modelo.nome,
                "nome_cor": cor.nome_cor,
            })
        elif pt.tecido:
            tecidos.append({
                "pt_id": str(pt.id),
                "id": str(pt.tecido.id),
                "nome": pt.tecido.nome,
                "lote_id": None,
                "codigo_lote": None,
                "largura_util_cm": float(pt.tecido.largura_util_cm),
                "gramatura_g_m2": float(pt.tecido.gramatura_g_m2),
                "valor_por_kg": float(pt.tecido.valor_por_kg),
                "encolhimento_pct": float(pt.tecido.encolhimento_pct),
                "peso_disponivel_kg": None,
                "cor_id": None,
                "modelo_nome": None,
                "nome_cor": None,
            })

    return {
        "id": str(pedido.id),
        "num_pedido": pedido.num_pedido,
        "data_pedido": pedido.data_pedido.isoformat(),
        "cliente": pedido.cliente,
        "status": pedido.status,
        "criado_em": pedido.criado_em.isoformat(),
        "tecidos": tecidos,
        "grupos_pecas": grupos_pecas,
    }


# ── Criação ───────────────────────────────────────────────────────────

def criar(db: Session, payload: PedidoCreate) -> dict:
    pedido = Pedido(
        num_pedido=payload.num_pedido,
        data_pedido=payload.data_pedido,
        cliente=payload.cliente,
    )
    db.add(pedido)
    db.flush()

    for tecido_id in payload.tecido_ids:
        db.add(PedidoTecido(pedido_id=pedido.id, tecido_id=tecido_id))

    db.commit()
    db.refresh(pedido)
    pedido.pecas  # força lazy load  # noqa: B018
    return _to_list_dict(pedido)


# ── Duplicar ──────────────────────────────────────────────────────────

def duplicar(db: Session, pedido_id: uuid.UUID) -> dict | None:
    original = (
        db.query(Pedido)
        .options(*_opts_full())
        .filter(Pedido.id == pedido_id)
        .first()
    )
    if not original:
        return None

    novo_num = proximo_numero(db)
    novo = Pedido(
        num_pedido=novo_num,
        data_pedido=date.today(),
        cliente=original.cliente,
    )
    db.add(novo)
    db.flush()

    for pt in original.pedido_tecidos:
        db.add(PedidoTecido(
            pedido_id=novo.id,
            lote_id=pt.lote_id,
            tecido_id=pt.tecido_id,
        ))

    for pp in original.pecas:
        db.add(PedidoPeca(
            pedido_id=novo.id,
            molde_id=pp.molde_id,
            quantidade=pp.quantidade,
            cor_id=pp.cor_id,
            tecido_id=pp.tecido_id,
        ))

    db.commit()
    db.refresh(novo)
    novo.pecas  # noqa: B018
    return _to_list_dict(novo)


# ── Atualização de campos do cabeçalho ───────────────────────────────

def atualizar(db: Session, pedido_id: uuid.UUID, payload: PedidoUpdate) -> dict | None:
    pedido = db.get(Pedido, pedido_id)
    if not pedido:
        return None
    for campo, valor in payload.model_dump(exclude_none=True).items():
        setattr(pedido, campo, valor)
    db.commit()
    return obter_detalhe(db, pedido_id)


def alterar_status(db: Session, pedido_id: uuid.UUID, payload: PedidoStatusUpdate) -> dict | None:
    if payload.status not in _STATUS_VALIDOS:
        return None
    pedido = db.get(Pedido, pedido_id)
    if not pedido:
        return None
    pedido.status = payload.status
    db.commit()
    return obter_detalhe(db, pedido_id)


# ── Excluir (soft delete) ─────────────────────────────────────────────

def excluir(db: Session, pedido_id: uuid.UUID) -> bool:
    pedido = db.get(Pedido, pedido_id)
    if not pedido:
        return False
    pedido.status = "cancelado"
    db.commit()
    return True


# ── Tecidos do pedido ─────────────────────────────────────────────────

def adicionar_tecido(db: Session, pedido_id: uuid.UUID, payload: PedidoTecidoCreate) -> dict | None:
    pedido = db.get(Pedido, pedido_id)
    if not pedido:
        return None

    if payload.lote_id:
        existe = (
            db.query(PedidoTecido)
            .filter(PedidoTecido.pedido_id == pedido_id, PedidoTecido.lote_id == payload.lote_id)
            .first()
        )
        if not existe:
            db.add(PedidoTecido(pedido_id=pedido_id, lote_id=payload.lote_id))
            db.commit()
    elif payload.tecido_id:
        existe = (
            db.query(PedidoTecido)
            .filter(PedidoTecido.pedido_id == pedido_id, PedidoTecido.tecido_id == payload.tecido_id)
            .first()
        )
        if not existe:
            db.add(PedidoTecido(pedido_id=pedido_id, tecido_id=payload.tecido_id))
            db.commit()

    return obter_detalhe(db, pedido_id)


def remover_tecido(db: Session, pedido_id: uuid.UUID, pt_id: uuid.UUID) -> dict | None:
    """Remove pelo ID do registro pedido_tecidos (pt_id)."""
    pedido = db.get(Pedido, pedido_id)
    if not pedido:
        return None
    db.query(PedidoTecido).filter(
        PedidoTecido.pedido_id == pedido_id,
        PedidoTecido.id == pt_id,
    ).delete(synchronize_session=False)
    db.commit()
    return obter_detalhe(db, pedido_id)


# ── Peças: adicionar grupo × tamanho ─────────────────────────────────

def adicionar_grupo_pecas(db: Session, pedido_id: uuid.UUID, payload: AdicionarGrupoPecaCreate) -> dict | None:
    pedido = db.get(Pedido, pedido_id)
    if not pedido:
        return None

    moldes = db.query(Molde).filter(Molde.grupo_id == payload.grupo_id).all()

    for tamanho, quantidade in payload.quantidades.items():
        if quantidade <= 0:
            continue
        moldes_t = [m for m in moldes if m.tamanho == tamanho]
        for m in moldes_t:
            db.query(PedidoPeca).filter(
                PedidoPeca.pedido_id == pedido_id,
                PedidoPeca.molde_id == m.id,
            ).delete(synchronize_session=False)
        for m in moldes_t:
            db.add(PedidoPeca(
                pedido_id=pedido_id,
                molde_id=m.id,
                quantidade=quantidade,
                cor_id=payload.cor_id,
                tecido_id=payload.tecido_id,
            ))

    db.commit()
    return obter_detalhe(db, pedido_id)


# ── Peças: remover grupo × tamanho ───────────────────────────────────

def remover_grupo_pecas(db: Session, pedido_id: uuid.UUID, grupo_id: uuid.UUID, tamanho: str) -> dict | None:
    molde_ids = [
        m.id
        for m in db.query(Molde).filter(Molde.grupo_id == grupo_id, Molde.tamanho == tamanho).all()
    ]
    if molde_ids:
        db.query(PedidoPeca).filter(
            PedidoPeca.pedido_id == pedido_id,
            PedidoPeca.molde_id.in_(molde_ids),
        ).delete(synchronize_session=False)
        db.commit()
    return obter_detalhe(db, pedido_id)


# ── Resumo de corte ───────────────────────────────────────────────────

def calcular_resumo_corte(db: Session, pedido_id: uuid.UUID) -> dict | None:
    pedido = (
        db.query(Pedido)
        .options(*_opts_full())
        .filter(Pedido.id == pedido_id)
        .first()
    )
    if not pedido:
        return None

    itens: list[dict] = []
    total_area_cm2 = 0.0
    total_pecas_corte = 0
    # key = "lote:<id>", "tec:<id>" ou None
    area_por_key: dict[str | None, float] = {}

    for pp in pedido.pecas:
        m = pp.molde
        mult = _MULT.get(m.tipo_corte, 1)
        qtd_corte = pp.quantidade * mult
        area = float(m.area_cm2) if m.area_cm2 is not None else 0.0
        area_total_linha = area * qtd_corte
        total_area_cm2 += area_total_linha
        total_pecas_corte += qtd_corte

        # Determina chave de agrupamento (nova hierarquia tem prioridade)
        cor = pp.cor_tecido
        tecido = pp.tecido
        if cor:
            key = f"cor:{pp.cor_id}"
            nome_fabric = f"{cor.modelo.nome} — {cor.nome_cor}"
        elif pp.tecido_id:
            key = f"tec:{pp.tecido_id}"
            nome_fabric = tecido.nome if tecido else None
        else:
            key = None
            nome_fabric = None

        area_por_key[key] = area_por_key.get(key, 0.0) + area_total_linha

        itens.append({
            "molde_id": str(m.id),
            "molde_nome": m.nome,
            "grupo_nome": m.grupo.nome if m.grupo else "—",
            "peca": m.peca,
            "tamanho": m.tamanho,
            "tipo_corte": m.tipo_corte,
            "quantidade_producao": pp.quantidade,
            "quantidade_corte": qtd_corte,
            "area_cm2": float(m.area_cm2) if m.area_cm2 is not None else None,
            "tecido_id": key,
            "tecido_nome": nome_fabric,
        })

    ordem = {"PP": 0, "P": 1, "M": 2, "G": 3, "GG": 4, "XGG": 5}
    itens.sort(key=lambda x: (
        x["tecido_nome"] or "zzz",
        x["grupo_nome"],
        x["peca"] or "",
        ordem.get(x["tamanho"] or "", 99),
    ))

    # Lookup de dados de tecido por chave
    # Novo: cor → via pedido_tecidos.lote.cor
    cor_lookup: dict[str, tuple] = {}  # cor_id_str → (largura, gramatura, valor_kg, encolhimento)
    for pt in pedido.pedido_tecidos:
        if pt.lote:
            cor = pt.lote.cor
            cor_lookup[str(cor.id)] = (
                float(cor.largura_util_cm),
                float(cor.gramatura_g_m2),
                float(pt.lote.valor_kg),
                float(cor.encolhimento_pct),
                f"{cor.modelo.nome} — {cor.nome_cor}",
            )

    # Legado: tecido
    tecido_lookup = {str(pt.tecido.id): pt.tecido for pt in pedido.pedido_tecidos if pt.tecido}

    estimativa_por_tecido = []
    est_metros_total = est_peso_total = est_custo_total = 0.0

    for key, area_cm2 in area_por_key.items():
        if not key or area_cm2 <= 0:
            continue

        if key.startswith("cor:"):
            cor_id_str = key[4:]
            dados = cor_lookup.get(cor_id_str)
            if not dados:
                continue
            largura, gramatura, valor_kg, encolhimento, nome_fabric = dados
        elif key.startswith("tec:"):
            tec_id_str = key[4:]
            t = tecido_lookup.get(tec_id_str)
            if not t:
                continue
            largura = float(t.largura_util_cm)
            gramatura = float(t.gramatura_g_m2)
            valor_kg = float(t.valor_por_kg)
            encolhimento = float(t.encolhimento_pct)
            nome_fabric = t.nome
        else:
            continue

        comp_minimo_m = (area_cm2 / largura) / 100
        comp_metros = aplicar_encolhimento(comp_minimo_m, encolhimento)
        peso_kg = metros_para_peso(comp_metros, gramatura, largura)
        custo = calcular_custo(peso_kg, valor_kg)

        estimativa_por_tecido.append({
            "tecido_id": key,
            "tecido_nome": nome_fabric,
            "area_cm2": round(area_cm2, 2),
            "estimativa_metros": round(comp_metros, 3),
            "estimativa_peso_kg": round(peso_kg, 3),
            "estimativa_custo": round(custo, 2),
        })
        est_metros_total += comp_metros
        est_peso_total += peso_kg
        est_custo_total += custo

    est_metros = est_peso = est_custo = None
    if estimativa_por_tecido:
        est_metros = round(est_metros_total, 3)
        est_peso = round(est_peso_total, 3)
        est_custo = round(est_custo_total, 2)
    elif pedido.pedido_tecidos and total_area_cm2 > 0:
        pt = pedido.pedido_tecidos[0]
        if pt.lote:
            cor = pt.lote.cor
            largura = float(cor.largura_util_cm)
            gramatura = float(cor.gramatura_g_m2)
            valor_kg = float(pt.lote.valor_kg)
            encolhimento = float(cor.encolhimento_pct)
        elif pt.tecido:
            t = pt.tecido
            largura = float(t.largura_util_cm)
            gramatura = float(t.gramatura_g_m2)
            valor_kg = float(t.valor_por_kg)
            encolhimento = float(t.encolhimento_pct)
        else:
            return _build_resumo(itens, total_pecas_corte, total_area_cm2, None, None, None, [])

        comp_minimo_m = (total_area_cm2 / largura) / 100
        comp_metros = aplicar_encolhimento(comp_minimo_m, encolhimento)
        peso_kg_total = metros_para_peso(comp_metros, gramatura, largura)
        est_metros = round(comp_metros, 3)
        est_peso = round(peso_kg_total, 3)
        est_custo = round(calcular_custo(peso_kg_total, valor_kg), 2)

    return _build_resumo(itens, total_pecas_corte, total_area_cm2, est_metros, est_peso, est_custo, estimativa_por_tecido)


def _build_resumo(itens, total_pecas_corte, total_area_cm2, est_metros, est_peso, est_custo, estimativa_por_tecido):
    return {
        "itens": itens,
        "total_pecas_corte": total_pecas_corte,
        "total_area_cm2": round(total_area_cm2, 2),
        "estimativa_metros": est_metros,
        "estimativa_peso_kg": est_peso,
        "estimativa_custo": est_custo,
        "estimativa_por_tecido": estimativa_por_tecido,
    }
