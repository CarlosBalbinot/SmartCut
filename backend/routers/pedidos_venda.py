import calendar
import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, computed_field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from middleware.permissions import require_permission
from models.cliente import Cliente
from models.condicao_pagamento import CondicaoPagamento
from models.pedido import ItemPedido, PedidoVenda, STATUS_VALIDOS
from models.produto import Produto
from models.produto_sku import ProdutoSKU
from models.venda import PrecoReferencia, TabelaPreco, Vendedor
from routers.produtos import buscar_sku_ativo_por_codigo
from routers.tes import buscar_tes_por_codigo
from schemas.venda_schema import (
    ItemPedidoVendaCreate,
    ItemPedidoVendaOut,
    ItensBulkCreateRequest,
    PedidoVendaCreate,
    PedidoVendaOut,
    PedidoVendaUpdate,
    PedidoStatusUpdate,
)
from services.pdf_venda_service import (
    gerar_pdf_corte,
    gerar_pdf_pedido,
    nome_arquivo_corte,
    nome_arquivo_pedido,
)
from services.venda_service import (
    SNAPSHOT_CLIENTE,
    aplicar_snapshot_cliente,
    pedido_sincronizavel,
    aplicar_comissao,
    calcular_subtotal_itens,
    get_ou_criar_empresa,
    proximo_numero,
    recalcular_pedido,
    resolver_preco_item,
)

router = APIRouter(prefix="/api/v1/pedidos-venda", tags=["pedidos_venda"])

_VER = require_permission("pedidos_ver", "ver")
_CRIAR = require_permission("pedidos_criar", "ver")
_EDITAR = require_permission("pedidos_editar", "ver")
_EXCLUIR = require_permission("pedidos_excluir", "ver")


# ── Schemas inline (campos ausentes no venda_schema.py) ──────────────────────


class _PedidoCreate(PedidoVendaCreate):
    tipo: str = "venda"
    cliente_id: Optional[int] = None


class _PedidoUpdate(PedidoVendaUpdate):
    cliente_id: Optional[int] = None


class _PedidoVendaOut(PedidoVendaOut):
    tipo: str = "venda"
    cliente_id: Optional[int] = None
    cliente_codigo: Optional[str] = None
    # Snapshot do % usado em comissao_valor — ver venda_service.aplicar_comissao.
    comissao_pct: Decimal = Decimal("0")
    comissao_origem: Optional[str] = None


class _ItemOut(ItemPedidoVendaOut):
    preco_manual: bool = False
    sku_codigo: Optional[str] = None
    descricao: Optional[str] = None
    desconto_percentual: Decimal = Decimal("0")
    desconto_tipo: str = "VALOR"
    # Só vem preenchido na resposta do PATCH que trocou o SKU — origem do
    # preço aplicado (ver venda_service.resolver_preco_item); None ali quer
    # dizer "sem preço, manteve o anterior".
    preco_origem: Optional[str] = None

    # Desconto em R$ com o nome usado pelo PATCH (espelha desconto_valor).
    @computed_field
    @property
    def desconto(self) -> Decimal:
        return Decimal(str(self.desconto_valor or 0))

    # Total líquido do item — mesma conta de calcular_subtotal_itens
    # (preco_total continua sendo o bruto quantidade * preço unitário).
    @computed_field
    @property
    def valor_total(self) -> Decimal:
        return (
            Decimal(str(self.preco_total or 0))
            - Decimal(str(self.desconto_valor or 0))
            + Decimal(str(self.acrescimo_valor or 0))
        )


class _PedidoVendaComItensOut(_PedidoVendaOut):
    itens: List[_ItemOut] = []


class _ItemUpdate(BaseModel):
    produto_id: Optional[uuid.UUID] = None
    cor: Optional[str] = None
    lote_id: Optional[uuid.UUID] = None
    qtd_p: Optional[int] = None
    qtd_m: Optional[int] = None
    qtd_g: Optional[int] = None
    qtd_gg: Optional[int] = None
    qtd_g1: Optional[int] = None
    qtd_g2: Optional[int] = None
    qtd_g3: Optional[int] = None
    preco_unitario: Optional[Decimal] = None
    tes_id: Optional[int] = None
    desconto_pct: Optional[Decimal] = None
    desconto_valor: Optional[Decimal] = None
    acrescimo_pct: Optional[Decimal] = None
    acrescimo_valor: Optional[Decimal] = None
    # Edição inline (grid de itens): quantidade do item produto/SKU,
    # desconto em R$ ou em %, TES e SKU pelo código digitado, descrição.
    quantidade: Optional[int] = None
    desconto: Optional[Decimal] = None
    desconto_percentual: Optional[Decimal] = None
    tes_codigo: Optional[str] = None
    sku_codigo: Optional[str] = None
    descricao: Optional[str] = None


class _AplicarTabelaRequest(BaseModel):
    tabela_preco_id: uuid.UUID


# ── Helpers ───────────────────────────────────────────────────────────────────
# Eager-load usado tanto para o item legado (grupo) quanto o item novo do
# catálogo fiscal (produto/sku) — cobre as propriedades
# ItemPedido.ref_codigo/descricao_completa usadas no schema de saída.

_ITEM_OPTS = [
    selectinload(PedidoVenda.cliente),
    selectinload(PedidoVenda.itens).selectinload(ItemPedido.grupo),
    selectinload(PedidoVenda.itens).selectinload(ItemPedido.produto),
    selectinload(PedidoVenda.itens).selectinload(ItemPedido.sku).selectinload(ProdutoSKU.produto_pai),
    selectinload(PedidoVenda.itens).selectinload(ItemPedido.sku).selectinload(ProdutoSKU.linha_item),
    selectinload(PedidoVenda.itens).selectinload(ItemPedido.sku).selectinload(ProdutoSKU.coluna_item),
]

_ITEM_DIRETO_OPTS = [
    selectinload(ItemPedido.grupo),
    selectinload(ItemPedido.produto),
    selectinload(ItemPedido.sku).selectinload(ProdutoSKU.produto_pai),
    selectinload(ItemPedido.sku).selectinload(ProdutoSKU.linha_item),
    selectinload(ItemPedido.sku).selectinload(ProdutoSKU.coluna_item),
]


def _load_com_itens(db: Session, pedido_id: uuid.UUID) -> PedidoVenda | None:
    return db.execute(select(PedidoVenda).where(PedidoVenda.id == pedido_id).options(*_ITEM_OPTS)).scalars().first()


def _cliente_ativo(db: Session, cliente_id: int) -> Cliente:
    cliente = db.get(Cliente, cliente_id)
    if not cliente or not cliente.ativo:
        raise HTTPException(status_code=422, detail="Cliente não encontrado")
    return cliente


def _sincronizar_representante(db: Session, pedido: PedidoVenda) -> None:
    """representante (texto) = nome do vendedor do pedido. O campo saiu das
    telas, mas ainda é lido pelo PDF do pedido e pelo painel do vendedor
    (novos clientes do mês) — por isso o backend mantém preenchido."""
    vendedor = db.get(Vendedor, pedido.vendedor_id) if pedido.vendedor_id else None
    pedido.representante = vendedor.nome if vendedor else None


def _exigir_aberto(pedido: PedidoVenda) -> None:
    if pedido.status != "Aberto":
        raise HTTPException(
            status_code=409,
            detail=f"Pedido {pedido.status} não pode ter os itens alterados.",
        )


_ORIGENS_TABELA = ("TABELA_SKU", "TABELA_PRODUTO", "TABELA_GRUPO")


def _descricao_padrao(item: ItemPedido) -> str | None:
    return (item.descricao_completa or "")[:120] or None


def _aplicar_desconto(item: ItemPedido, limitar: bool = False) -> None:
    """Recalcula bruto (preco_total) e o par desconto R$/% do item conforme
    desconto_tipo: PERCENTUAL mantém o % e recalcula o R$; VALOR mantém o R$
    e recalcula o %. VALOR maior que o bruto → 422, ou limitado ao bruto
    quando limitar=True (aplicar-tabela, em lote)."""
    bruto = Decimal(str(item.preco_unitario or 0)) * item.quantidade_total
    item.preco_total = bruto
    if item.desconto_tipo == "PERCENTUAL":
        pct = Decimal(str(item.desconto_percentual or 0))
        valor = (bruto * pct / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        valor = Decimal(str(item.desconto_valor or 0))
        if valor > bruto:
            if not limitar:
                raise HTTPException(status_code=422, detail="Desconto maior que o valor do item")
            valor = bruto
        pct = (valor / bruto * 100) if bruto else Decimal("0")
        pct = pct.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    item.desconto_valor = float(valor)
    item.desconto_percentual = pct
    item.desconto_pct = float(pct)


def _itens_com_grupo(db: Session, pedido_id: uuid.UUID):
    return (
        db.execute(
            select(ItemPedido)
            .where(ItemPedido.pedido_id == pedido_id)
            .options(*_ITEM_DIRETO_OPTS)
            .order_by(ItemPedido.id)
        )
        .scalars()
        .all()
    )


# ── Número sequencial ─────────────────────────────────────────────────────────


@router.get("/proximo-numero", dependencies=[Depends(_VER)])
def get_proximo_numero(tipo: str = "venda", db: Session = Depends(get_db)):
    return {"data": proximo_numero(db, tipo), "error": None}


# ── Métricas de vendas (dashboard executivo) ──────────────────────────────────
# Portado do router legado routers/pedidos.py (item 7.2): era o único endpoint
# daquele router com consumo real no frontend (PainelFinanceiro). Os demais
# (resumo-corte, relatorio-pdf, duplicar, tecidos/peças do pedido) ficaram sem
# consumo e foram descartados junto com a interface antiga de pedidos.


def _ultimos_meses(n: int) -> list[tuple[int, int]]:
    """Lista (ano, mes) dos últimos `n` meses, do mais antigo ao atual."""
    hoje = date.today()
    chaves = []
    m, a = hoje.month, hoje.year
    for _ in range(n):
        chaves.append((a, m))
        m -= 1
        if m == 0:
            m, a = 12, a - 1
    chaves.reverse()
    return chaves


def _serie_mensal_pedidos(db: Session, meses: int = 12) -> list[dict]:
    chaves = _ultimos_meses(meses)
    data_min = date(chaves[0][0], chaves[0][1], 1)

    rows = db.execute(
        select(
            func.strftime("%Y-%m", PedidoVenda.data_emissao).label("chave"),
            func.sum(PedidoVenda.total_pedido).label("total"),
        )
        .where(PedidoVenda.tipo == "venda", PedidoVenda.data_emissao >= data_min)
        .group_by("chave")
    ).all()
    mapa = {r.chave: float(r.total or 0) for r in rows}

    return [{"mes": m, "ano": a, "total": mapa.get(f"{a:04d}-{m:02d}", 0.0)} for a, m in chaves]


def _serie_semanal_pedidos(db: Session, semanas: int = 8) -> list[dict]:
    hoje = date.today()
    data_min = hoje - timedelta(weeks=semanas)

    rows = db.execute(
        select(
            func.strftime("%Y-%W", PedidoVenda.data_emissao).label("chave"),
            func.sum(PedidoVenda.total_pedido).label("total"),
        )
        .where(PedidoVenda.tipo == "venda", PedidoVenda.data_emissao >= data_min)
        .group_by("chave")
    ).all()
    mapa = {r.chave: float(r.total or 0) for r in rows}

    chaves = []
    d = hoje
    for _ in range(semanas):
        chaves.append(d.strftime("%Y-%W"))
        d -= timedelta(weeks=1)
    chaves.reverse()

    return [{"semana": chave, "total": mapa.get(chave, 0.0)} for chave in chaves]


# Rota fixa registrada antes de /{pedido_id} — senão "/metricas" casaria com o
# parâmetro UUID e retornaria 422 em vez do payload.
@router.get("/metricas", dependencies=[Depends(_VER)])
def metricas_vendas(
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Métricas de desempenho de vendas para o dashboard executivo.

    total_faturado/total_pedidos/ticket_medio/top_clientes respeitam o
    período (data_inicio/data_fim, padrão: mês atual). As séries temporais
    (faturamento_por_mes/por_semana) são sempre a janela móvel mais recente,
    independente do período selecionado — são gráficos de tendência.
    """
    if not data_inicio or not data_fim:
        hoje = date.today()
        data_inicio = hoje.replace(day=1)
        data_fim = date(hoje.year, hoje.month, calendar.monthrange(hoje.year, hoje.month)[1])

    pedidos_periodo = (
        db.execute(
            select(PedidoVenda).where(
                PedidoVenda.tipo == "venda",
                PedidoVenda.data_emissao >= data_inicio,
                PedidoVenda.data_emissao <= data_fim,
            )
        )
        .scalars()
        .all()
    )

    total_faturado = sum(float(p.total_pedido or 0) for p in pedidos_periodo)
    total_pedidos = len(pedidos_periodo)
    ticket_medio = (total_faturado / total_pedidos) if total_pedidos else 0.0

    clientes_map: dict[str, dict] = {}
    for p in pedidos_periodo:
        nome = p.cliente_razao_social or "—"
        agg = clientes_map.setdefault(nome, {"cliente": nome, "total_pedidos": 0, "total_valor": 0.0})
        agg["total_pedidos"] += 1
        agg["total_valor"] += float(p.total_pedido or 0)
    top_clientes = sorted(clientes_map.values(), key=lambda x: x["total_valor"], reverse=True)[:5]

    return {
        "data": {
            "total_faturado": total_faturado,
            "total_pedidos": total_pedidos,
            "ticket_medio": ticket_medio,
            "faturamento_por_mes": _serie_mensal_pedidos(db, meses=12),
            "top_clientes": top_clientes,
            "faturamento_por_semana": _serie_semanal_pedidos(db, semanas=8),
        },
        "error": None,
    }


# ── CRUD pedidos ──────────────────────────────────────────────────────────────


@router.get("/", dependencies=[Depends(_VER)])
def listar(tipo: str | None = None, db: Session = Depends(get_db)):
    """Lista com os nomes já resolvidos (vendedor, tabela, condição de
    pagamento) numa única consulta — outer join: sem vendedor/tabela/
    condição o nome vem null. tipo_preco é o "avista"/"aprazo" da tabela
    (campo `condicoes`), não a condição de pagamento."""
    q = (
        select(
            PedidoVenda,
            Vendedor.nome,
            TabelaPreco.nome,
            CondicaoPagamento.descricao,
        )
        .outerjoin(Vendedor, Vendedor.id == PedidoVenda.vendedor_id)
        .outerjoin(TabelaPreco, TabelaPreco.id == PedidoVenda.tabela_preco_id)
        .outerjoin(CondicaoPagamento, CondicaoPagamento.id == PedidoVenda.condicao_pagamento_id)
        # cliente_codigo na resposta lê o relacionamento — carrega junto.
        .options(selectinload(PedidoVenda.cliente))
        .order_by(PedidoVenda.data_emissao.desc(), PedidoVenda.numero.desc())
    )
    if tipo:
        q = q.where(PedidoVenda.tipo == tipo)
    data = []
    for pedido, vendedor_nome, tabela_nome, condicao_desc in db.execute(q).all():
        d = _PedidoVendaOut.model_validate(pedido).model_dump()
        d.update(
            {
                "vendedor_nome": vendedor_nome,
                "tabela_preco_nome": tabela_nome,
                "condicao_pagamento_descricao": condicao_desc,
                "tipo_preco": pedido.condicoes,
                "total": d["total_pedido"],
            }
        )
        data.append(d)
    return {"data": data, "error": None}


@router.post("/", dependencies=[Depends(_CRIAR)])
def criar(payload: _PedidoCreate, db: Session = Depends(get_db)):
    numero = proximo_numero(db, payload.tipo)
    # exclude_unset: campos não enviados ficam de fora do kwargs e caem nos
    # defaults do model (ex.: desconto_geral_pct=0.0) em vez de None, que
    # quebraria colunas NOT NULL.
    dados = payload.model_dump(exclude_unset=True)
    cliente_id = dados.pop("cliente_id", None)
    # Pedido de venda novo exige cliente do cadastro (a cópia cliente_* vem
    # dele). Encaixe rápido é pedido interno, sem cliente — segue livre.
    # Pedidos antigos sem vínculo continuam editáveis (PATCH não exige).
    if payload.tipo == "venda" and cliente_id is None:
        raise HTTPException(status_code=422, detail="Selecione um cliente do cadastro")
    cliente = _cliente_ativo(db, cliente_id) if cliente_id is not None else None
    if cliente:
        # Com cliente do cadastro, a cópia vem dele — o que o front mandou é ignorado.
        for campo in SNAPSHOT_CLIENTE:
            dados.pop(campo, None)
    pedido = PedidoVenda(numero=numero, **dados)
    if cliente:
        aplicar_snapshot_cliente(pedido, cliente)
    _sincronizar_representante(db, pedido)
    aplicar_comissao(db, pedido)
    db.add(pedido)
    db.commit()
    pedido = _load_com_itens(db, pedido.id)
    return {"data": _PedidoVendaComItensOut.model_validate(pedido), "error": None}


@router.get("/{pedido_id}", dependencies=[Depends(_VER)])
def get_one(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    pedido = _load_com_itens(db, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return {"data": _PedidoVendaComItensOut.model_validate(pedido), "error": None}


@router.patch("/{pedido_id}", dependencies=[Depends(_EDITAR)])
def atualizar(pedido_id: uuid.UUID, payload: _PedidoUpdate, db: Session = Depends(get_db)):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    antes = (pedido.vendedor_id, pedido.tabela_preco_id)
    dados = payload.model_dump(exclude_unset=True)

    # Troca de cliente: só com pedido Aberto; não mexe em itens, preços,
    # vendedor nem tabela. null não desvincula (o pedido precisa de cliente).
    # O MESMO cliente ressincroniza a cópia com o cadastro — mas só se o
    # pedido ainda pode mudar (Aberto, sem NF-e); senão é ignorado.
    novo_cliente_id = dados.pop("cliente_id", None)
    cliente_snapshot = None
    if novo_cliente_id is not None and novo_cliente_id != pedido.cliente_id:
        if pedido.status != "Aberto":
            raise HTTPException(
                status_code=409,
                detail=f"Pedido {pedido.status} não pode ter o cliente alterado.",
            )
        cliente_snapshot = _cliente_ativo(db, novo_cliente_id)
    elif novo_cliente_id is not None and pedido_sincronizavel(db, pedido):
        atual = db.get(Cliente, novo_cliente_id)
        # Cliente inativado depois: mantém a cópia em vez de travar o salvar.
        if atual is not None and atual.ativo:
            cliente_snapshot = atual

    # Pedido com cliente do cadastro: endereço/contato vindos do front são
    # ignorados — a cópia só vem do cadastro. Pedido de cliente não
    # cadastrado (cliente_id nulo) continua aceitando a cópia digitada.
    if pedido.cliente_id is not None or cliente_snapshot is not None:
        for campo in SNAPSHOT_CLIENTE:
            dados.pop(campo, None)

    for field, val in dados.items():
        setattr(pedido, field, val)
    if cliente_snapshot is not None:
        aplicar_snapshot_cliente(pedido, cliente_snapshot)
    # Só na troca de vendedor — pedidos existentes mantêm o representante gravado.
    if pedido.vendedor_id != antes[0]:
        _sincronizar_representante(db, pedido)
    # Comissão é snapshot: só muda se trocou vendedor/tabela com o pedido
    # Aberto — mudar o cadastro do vendedor não mexe em pedidos existentes.
    if pedido.status == "Aberto" and (pedido.vendedor_id, pedido.tabela_preco_id) != antes:
        aplicar_comissao(db, pedido)
    recalcular_pedido(db, pedido_id)
    db.commit()
    pedido = _load_com_itens(db, pedido_id)
    return {"data": _PedidoVendaComItensOut.model_validate(pedido), "error": None}


# Transições permitidas: Aberto -> Fechado, Aberto -> Cancelado,
# Fechado -> Aberto (só se ainda não tem NF-e emitida). Fechado -> Cancelado
# e qualquer transição a partir de Cancelado não são permitidas.
def _validar_transicao_status(atual: str, novo: str, nfe_id: int | None) -> None:
    if novo not in STATUS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Status inválido: {novo}")
    if atual == novo:
        raise HTTPException(status_code=400, detail="O pedido já está neste status.")
    if atual == "Aberto" and novo in ("Fechado", "Cancelado"):
        return
    if atual == "Fechado" and novo == "Aberto":
        if nfe_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Não é possível reabrir um pedido com NF-e emitida.",
            )
        return
    raise HTTPException(status_code=400, detail=f"Transição de {atual} para {novo} não permitida.")


@router.patch("/{pedido_id}/status", dependencies=[Depends(_EDITAR)])
def alterar_status(pedido_id: uuid.UUID, payload: PedidoStatusUpdate, db: Session = Depends(get_db)):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    _validar_transicao_status(pedido.status, payload.status, pedido.nfe_id)
    pedido.status = payload.status
    db.commit()
    pedido = _load_com_itens(db, pedido_id)
    return {"data": _PedidoVendaComItensOut.model_validate(pedido), "error": None}


@router.delete("/{pedido_id}", dependencies=[Depends(_EXCLUIR)])
def deletar(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    """Soft delete — mantido por compatibilidade. O fluxo novo usa
    PATCH /{pedido_id}/status com {"status": "Cancelado"} (botão
    "Cancelar Pedido" no frontend)."""
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    pedido.status = "Cancelado"
    db.commit()
    return {"data": None, "error": None}


# ── Itens ─────────────────────────────────────────────────────────────────────


@router.post("/{pedido_id}/itens", dependencies=[Depends(_EDITAR)])
def adicionar_item(
    pedido_id: uuid.UUID,
    payload: ItemPedidoVendaCreate,
    db: Session = Depends(get_db),
):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    preco_unit = payload.preco_unitario
    # Preço digitado no payload tem prioridade (regra já existente); sem ele,
    # vem de resolver_preco_item e o item não conta como preço manual.
    preco_manual = preco_unit is not None
    if preco_unit is None:
        produto = db.get(Produto, payload.produto_id) if payload.produto_id else None
        preco_unit, _ = resolver_preco_item(
            db,
            None,
            pedido.tabela_preco_id,
            pedido.condicoes or "",
            produto=produto,
            grupo_id=payload.grupo_id,
        )

    # TES do item: usa o que veio explícito no payload; senão cai para o
    # TES padrão do cabeçalho do pedido. A regra pedida ("TES do produto
    # tem prioridade") não é implementável hoje — ItemPedido.grupo_id
    # aponta para GrupoMolde (catálogo de corte), não para o cadastro
    # Produto que tem tes_saida_id; as duas tabelas não têm vínculo entre
    # si (isso é o que a Fase 3, ainda não feita, deveria resolver).
    tes_id = payload.tes_id if payload.tes_id is not None else pedido.tes_id

    # Só % informado → desconto percentual; caso contrário, em R$.
    desconto_pct = Decimal(str(payload.desconto_pct or 0))
    desconto_valor = Decimal(str(payload.desconto_valor or 0))
    percentual = desconto_pct > 0 and desconto_valor == 0

    item = ItemPedido(
        pedido_id=pedido_id,
        grupo_id=payload.grupo_id,
        produto_id=payload.produto_id,
        lote_id=payload.lote_id,
        cor=payload.cor,
        qtd_p=payload.qtd_p or 0,
        qtd_m=payload.qtd_m or 0,
        qtd_g=payload.qtd_g or 0,
        qtd_gg=payload.qtd_gg or 0,
        qtd_g1=payload.qtd_g1 or 0,
        qtd_g2=payload.qtd_g2 or 0,
        qtd_g3=payload.qtd_g3 or 0,
        preco_unitario=preco_unit or Decimal("0"),
        preco_manual=preco_manual,
        tes_id=tes_id,
        desconto_tipo="PERCENTUAL" if percentual else "VALOR",
        desconto_percentual=desconto_pct if percentual else Decimal("0"),
        desconto_valor=float(desconto_valor),
        acrescimo_pct=float(payload.acrescimo_pct or 0),
        acrescimo_valor=float(payload.acrescimo_valor or 0),
    )
    _aplicar_desconto(item)
    db.add(item)
    # flush obrigatório: a sessão roda com autoflush=False (database.py), e
    # recalcular_pedido faz um SELECT novo em itens_pedido — sem o flush,
    # esse item recém-criado fica invisível para o próprio recálculo do
    # total desta mesma requisição.
    db.flush()
    item.descricao = _descricao_padrao(item)
    recalcular_pedido(db, pedido_id)
    db.commit()
    db.refresh(item)
    return {"data": _ItemOut.model_validate(item), "error": None}


@router.patch("/{pedido_id}/itens/{item_id}", dependencies=[Depends(_EDITAR)])
def editar_item(
    pedido_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: _ItemUpdate,
    db: Session = Depends(get_db),
):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    item = (
        db.execute(
            select(ItemPedido)
            .where(
                ItemPedido.id == item_id,
                ItemPedido.pedido_id == pedido_id,
            )
            .options(*_ITEM_DIRETO_OPTS)
        )
        .scalars()
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    _exigir_aberto(pedido)

    dados = payload.model_dump(exclude_unset=True)
    preco_origem: str | None = None

    # Nomes antigos do body → nomes novos (desconto em R$ / em %).
    if "desconto_valor" in dados:
        dados.setdefault("desconto", dados.pop("desconto_valor"))
    if "desconto_pct" in dados:
        dados.setdefault("desconto_percentual", dados.pop("desconto_pct"))
    if "desconto" in dados and "desconto_percentual" in dados:
        raise HTTPException(status_code=422, detail="Informe desconto (R$) ou desconto_percentual, não os dois.")

    if "tes_codigo" in dados:
        codigo = (dados.pop("tes_codigo") or "").strip()
        tes = buscar_tes_por_codigo(db, codigo)
        if not tes:
            raise HTTPException(status_code=422, detail=f"Código de TES inválido: {codigo}")
        dados["tes_id"] = tes.id

    # Troca de SKU: descrição e preço vêm do novo SKU; quantidade, TES e o
    # desconto (conforme desconto_tipo) são mantidos.
    if "sku_codigo" in dados:
        codigo = (dados.pop("sku_codigo") or "").strip()
        if item.grupo_id is not None:
            raise HTTPException(status_code=422, detail="Item de corte não permite troca de produto.")
        sku = buscar_sku_ativo_por_codigo(db, codigo)
        if not sku:
            raise HTTPException(status_code=422, detail=f"Código de produto inválido: {codigo}")
        # FK e relationship juntos: com autoflush=False o FK só mudaria no
        # flush, e descricao_completa/quantidade_total leem sku_id/produto_id.
        item.sku_id, item.sku = sku.id, sku
        item.produto_id, item.produto = sku.produto_pai_id, sku.produto_pai
        item.descricao = _descricao_padrao(item)
        if "preco_unitario" not in dados:
            preco, preco_origem = resolver_preco_item(
                db,
                sku,
                pedido.tabela_preco_id,
                pedido.condicoes or "",
            )
            # Sem preço em lugar nenhum: mantém o atual (preco_origem=None
            # na resposta sinaliza isso para a tela).
            if preco is not None:
                item.preco_unitario = preco
            item.preco_manual = False
        dados["_troca_sku"] = True

    if "descricao" in dados:
        descricao = (dados.pop("descricao") or "").strip().upper()
        if len(descricao) > 120:
            raise HTTPException(status_code=422, detail="Descrição deve ter no máximo 120 caracteres.")
        item.descricao = descricao or _descricao_padrao(item)

    if "quantidade" in dados:
        if dados["quantidade"] is None or dados["quantidade"] <= 0:
            raise HTTPException(status_code=422, detail="Quantidade deve ser maior que zero.")
        if item.grupo_id is not None:
            # Item legado de corte: quantidade vem da grade qtd_p..qtd_g3
            # (ver ItemPedido.quantidade_total) — "quantidade" seria ignorado.
            raise HTTPException(
                status_code=422,
                detail="Item de corte usa quantidades por tamanho (qtd_p..qtd_g3).",
            )
    if "preco_unitario" in dados:
        if dados["preco_unitario"] is None or dados["preco_unitario"] < 0:
            raise HTTPException(status_code=422, detail="Preço unitário não pode ser negativo.")
        item.preco_manual = True

    if "desconto_percentual" in dados:
        pct = dados.pop("desconto_percentual")
        if pct is None or pct < 0 or pct > 100:
            raise HTTPException(status_code=422, detail="Desconto percentual deve estar entre 0 e 100.")
        item.desconto_tipo = "PERCENTUAL"
        item.desconto_percentual = pct
        dados["_desconto"] = True
    if "desconto" in dados:
        valor = dados.pop("desconto")
        if valor is None or valor < 0:
            raise HTTPException(status_code=422, detail="Desconto não pode ser negativo.")
        item.desconto_tipo = "VALOR"
        item.desconto_valor = float(valor)
        dados["_desconto"] = True

    for field in ("acrescimo_pct", "acrescimo_valor"):
        if dados.get(field) is not None:
            dados[field] = float(dados[field])

    for field, val in dados.items():
        if not field.startswith("_"):
            setattr(item, field, val)

    campos_valor = {
        "quantidade",
        "preco_unitario",
        "_desconto",
        "_troca_sku",
        "qtd_p",
        "qtd_m",
        "qtd_g",
        "qtd_gg",
        "qtd_g1",
        "qtd_g2",
        "qtd_g3",
    }
    if campos_valor & dados.keys():
        _aplicar_desconto(item)

    db.flush()
    recalcular_pedido(db, pedido_id)
    db.commit()
    db.refresh(item)
    db.refresh(pedido)
    item.preco_origem = preco_origem
    itens = db.execute(select(ItemPedido).where(ItemPedido.pedido_id == pedido_id)).scalars().all()
    return {
        "data": {
            "item": _ItemOut.model_validate(item),
            "totais": {
                "subtotal": calcular_subtotal_itens(itens),
                "total": pedido.total_pedido,
            },
        },
        "error": None,
    }


@router.post("/{pedido_id}/aplicar-tabela", dependencies=[Depends(_EDITAR)])
def aplicar_tabela(
    pedido_id: uuid.UUID,
    payload: _AplicarTabelaRequest,
    db: Session = Depends(get_db),
):
    """Reprecifica TODOS os itens pela tabela — inclusive os com
    preco_manual=True, que voltam a False. Item sem preço na tabela (SKU,
    produto pai ou grupo) mantém o preço atual e é devolvido em
    "sem_preco". Desconto PERCENTUAL mantém o %; VALOR mantém o R$ (limitado
    ao novo bruto)."""
    pedido = _load_com_itens(db, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    _exigir_aberto(pedido)
    if not db.get(TabelaPreco, payload.tabela_preco_id):
        raise HTTPException(status_code=404, detail="Tabela de preço não encontrada")

    if pedido.tabela_preco_id != payload.tabela_preco_id:
        pedido.tabela_preco_id = payload.tabela_preco_id
        aplicar_comissao(db, pedido)
    sem_preco: list[str] = []
    for item in pedido.itens:
        preco, origem = resolver_preco_item(
            db,
            item.sku,
            payload.tabela_preco_id,
            pedido.condicoes or "",
            produto=item.produto,
            grupo_id=item.grupo_id,
        )
        if origem not in _ORIGENS_TABELA:
            sem_preco.append(item.ref_codigo or item.descricao or str(item.id))
            continue
        item.preco_unitario = preco
        item.preco_manual = False
        _aplicar_desconto(item, limitar=True)

    db.flush()
    recalcular_pedido(db, pedido_id)
    db.commit()
    db.expire_all()
    pedido = _load_com_itens(db, pedido_id)
    return {
        "data": {
            "pedido": _PedidoVendaComItensOut.model_validate(pedido),
            "sem_preco": sem_preco,
        },
        "error": None,
    }


@router.delete("/{pedido_id}/itens/{item_id}", dependencies=[Depends(_EDITAR)])
def remover_item(pedido_id: uuid.UUID, item_id: uuid.UUID, db: Session = Depends(get_db)):
    item = (
        db.execute(
            select(ItemPedido).where(
                ItemPedido.id == item_id,
                ItemPedido.pedido_id == pedido_id,
            )
        )
        .scalars()
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    db.delete(item)
    recalcular_pedido(db, pedido_id)
    db.commit()
    return {"data": None, "error": None}


# Item do fluxo novo (grade visual produto pai/SKU ou avulso) — um
# ItemPedido por célula/produto preenchido, sem grupo_id (ver
# models/pedido.py). Transação única: qualquer falha reverte todos.
@router.post("/{pedido_id}/itens/bulk", dependencies=[Depends(_EDITAR)])
def adicionar_itens_bulk(
    pedido_id: uuid.UUID,
    payload: ItensBulkCreateRequest,
    db: Session = Depends(get_db),
):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    if not payload.itens:
        raise HTTPException(status_code=400, detail="Nenhum item informado.")

    criados: list[ItemPedido] = []
    try:
        for it in payload.itens:
            sku = None
            if it.sku_id is not None:
                sku = db.get(ProdutoSKU, it.sku_id)
                if not sku or sku.produto_pai_id != it.produto_id:
                    raise ValueError(f"SKU {it.sku_id} inválido para o produto informado.")
            if it.quantidade <= 0:
                raise ValueError("Quantidade deve ser maior que zero.")

            # Com tabela no pedido, o preço da tabela (SKU > produto pai)
            # prevalece sobre o que veio da grade; fora da tabela, fica o do
            # payload (a tela já manda sku.preco_manual > pai.preco_venda).
            preco_unit = Decimal(str(it.preco_unitario))
            preco, origem = resolver_preco_item(
                db,
                sku,
                pedido.tabela_preco_id,
                pedido.condicoes or "",
                produto=db.get(Produto, it.produto_id),
            )
            if origem in _ORIGENS_TABELA:
                preco_unit = preco

            desconto_pct = Decimal(str(it.desconto_pct or 0))
            item = ItemPedido(
                pedido_id=pedido_id,
                grupo_id=None,
                produto_id=it.produto_id,
                sku_id=it.sku_id,
                quantidade=it.quantidade,
                preco_unitario=preco_unit,
                preco_manual=False,
                tes_id=it.tes_id if it.tes_id is not None else pedido.tes_id,
                desconto_tipo="PERCENTUAL" if desconto_pct > 0 else "VALOR",
                desconto_percentual=desconto_pct,
                desconto_valor=0.0,
            )
            _aplicar_desconto(item)
            db.add(item)
            criados.append(item)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    db.flush()
    for item in criados:
        item.descricao = _descricao_padrao(item)
    recalcular_pedido(db, pedido_id)
    db.commit()
    for item in criados:
        db.refresh(item)
    return {"data": [_ItemOut.model_validate(i) for i in criados], "error": None}


# ── PDFs ──────────────────────────────────────────────────────────────────────


@router.get("/{pedido_id}/pdf-pedido", dependencies=[Depends(_VER)])
def pdf_pedido(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    itens = _itens_com_grupo(db, pedido_id)
    empresa = get_ou_criar_empresa(db)

    precos_ref = {}
    grupo_ids = {item.grupo_id for item in itens if item.grupo_id is not None}
    if pedido.tabela_preco_id and grupo_ids:
        refs = (
            db.execute(
                select(PrecoReferencia).where(
                    PrecoReferencia.tabela_id == pedido.tabela_preco_id,
                    PrecoReferencia.grupo_id.in_(grupo_ids),
                )
            )
            .scalars()
            .all()
        )
        precos_ref = {str(r.grupo_id): r for r in refs}

    pdf_bytes = gerar_pdf_pedido(pedido, itens, empresa, precos_ref)
    filename = nome_arquivo_pedido(pedido)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


@router.get("/{pedido_id}/pdf-corte", dependencies=[Depends(_VER)])
def pdf_corte(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    # Formulário de corte é específico do catálogo de GrupoMolde — itens do
    # catálogo fiscal novo (produto/sku, sem grupo_id) não entram aqui.
    itens = [i for i in _itens_com_grupo(db, pedido_id) if i.grupo_id is not None]
    pdf_bytes = gerar_pdf_corte(pedido, itens)
    filename = nome_arquivo_corte(pedido)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


# ── Encaixe (placeholder) ─────────────────────────────────────────────────────


@router.post("/{pedido_id}/gerar-encaixe", status_code=202, dependencies=[Depends(_EDITAR)])
def gerar_encaixe(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return {"data": {"status": "aguardando", "pedido_id": str(pedido_id)}, "error": None}
