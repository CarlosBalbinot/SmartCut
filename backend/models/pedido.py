import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
    func,
    select,
    update,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship
from sqlalchemy.orm.attributes import set_committed_value

from database import Base

STATUS_VALIDOS = ("Aberto", "Fechado", "Cancelado")

INDICADOR_PRESENCA_VALIDOS = ("Presencial", "Internet", "Teleatendimento", "Outros")

# ItemPedido.desconto_tipo — qual dos dois valores é a fonte da verdade
# quando quantidade/preço mudam: PERCENTUAL mantém o % e recalcula o R$;
# VALOR mantém o R$ e recalcula o %.
DESCONTO_TIPOS = ("PERCENTUAL", "VALOR")

# PedidoVenda.comissao_origem
COMISSAO_ORIGENS = ("VINCULO", "PADRAO_VENDEDOR", "SEM_VENDEDOR", "NENHUMA")

TIPO_FRETE_VALIDOS = (
    "Sem Frete",
    "CIF",
    "FOB",
    "Por conta de terceiros",
    "Próprio",
    "Sem Ocorrência",
)


class PedidoVenda(Base):
    __tablename__ = "pedidos_venda"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="venda")
    data_emissao: Mapped[date] = mapped_column(Date, nullable=False)
    prazo_entrega_dias: Mapped[int | None] = mapped_column(Integer, default=20)
    # "avista" / "aprazo" — usado hoje para escolher entre preco_avista e
    # preco_aprazo na tabela de preços (ver services/venda_service.get_preco
    # e o preenchimento automático de preço no frontend). Não é texto livre
    # de condição de pagamento apesar do nome — por isso NÃO foi renomeado
    # para condicoes_legado nem substituído: fazer isso quebraria o
    # preenchimento automático de preço em todo pedido, novo ou antigo.
    # O novo módulo de Condições de Pagamento (parcelas) é independente
    # disso — ver condicao_pagamento_id abaixo.
    condicoes: Mapped[str | None] = mapped_column(String(20))
    # Condição de pagamento (parcelamento) — módulo novo, independente do
    # campo `condicoes` acima. Com FK real (diferente de tes_id/nfe_id
    # históricos): a tabela condicoes_pagamento já existe nesta mesma leva
    # de mudanças, então não há o problema de ordem que levou aqueles
    # campos a ficarem sem FK.
    condicao_pagamento_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("condicoes_pagamento.id"), nullable=True
    )
    # Data base para calcular as parcelas quando a condição é do tipo
    # "intervalo" (dias a partir da emissão) — usada tanto pelo preview no
    # frontend quanto por uma futura geração automática de parcelas.
    primeiro_vencimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    vendedor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("vendedores.id"), nullable=True
    )
    tabela_preco_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tabelas_preco.id"), nullable=True
    )
    # Cliente do cadastro. Os campos cliente_* abaixo são a cópia (snapshot)
    # usada por PDF, NF-e, portal e relatórios — preenchida pelo backend a
    # partir do cadastro ao criar o pedido ou trocar o cliente (ver
    # routers/pedidos_venda._aplicar_snapshot_cliente). Nulo em pedidos de
    # cliente não cadastrado, que mantêm a cópia digitada.
    cliente_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clientes.id"), nullable=True)
    cliente_razao_social: Mapped[str | None] = mapped_column(String(200))
    cliente_cnpj: Mapped[str | None] = mapped_column(String(20))
    cliente_ie: Mapped[str | None] = mapped_column(String(30))
    cliente_endereco: Mapped[str | None] = mapped_column(Text)
    cliente_numero: Mapped[str | None] = mapped_column(String(20))
    cliente_bairro: Mapped[str | None] = mapped_column(String(100))
    cliente_cidade: Mapped[str | None] = mapped_column(String(100))
    cliente_uf: Mapped[str | None] = mapped_column(String(2))
    cliente_cep: Mapped[str | None] = mapped_column(String(10))
    cliente_codigo_ibge_municipio: Mapped[str | None] = mapped_column(String(7))
    cliente_codigo_pais: Mapped[str | None] = mapped_column(String(10), default="1058")
    cliente_telefone: Mapped[str | None] = mapped_column(String(20))
    cliente_email: Mapped[str | None] = mapped_column(String(100))
    representante: Mapped[str | None] = mapped_column(String(100))

    # "Aberto" / "Fechado" / "Cancelado" — ver STATUS_VALIDOS. Transições
    # validadas em routers/pedidos_venda.py (PATCH /{id}/status).
    status: Mapped[str] = mapped_column(String(20), default="Aberto", nullable=False)

    total_pedido: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    comissao_valor: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    # Snapshot do % (0–100) usado no último cálculo de comissao_valor e de
    # onde ele veio — ver COMISSAO_ORIGENS.
    comissao_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    comissao_origem: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ── Fiscal / Financeiro ──────────────────────────────────────────────
    # TES padrão do cabeçalho — a tabela "tes" já existe (Fase 2), então
    # leva FK de verdade (diferente de nfe_id abaixo, cuja tabela ainda
    # não existe).
    tes_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tes.id"), nullable=True)
    desconto_geral_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    desconto_geral_valor: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    acrescimo_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    acrescimo_valor: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    valor_frete: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    valor_seguro: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    valor_despesas: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    indicador_presenca: Mapped[str] = mapped_column(String(20), nullable=False, default="Presencial")
    informacoes_adicionais: Mapped[str | None] = mapped_column(Text, nullable=True)
    observacoes_internas: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Vínculo com a NF-e emitida (Fase 4) — tabela "nfe" ainda não existe,
    # por isso sem ForeignKey explícito (evita quebrar o Alembic antes da
    # tabela existir). É o campo usado para decidir se um pedido Fechado
    # pode ser reaberto (só se nfe_id for nulo).
    nfe_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Transporte ────────────────────────────────────────────────────────
    # Não listado no escopo original da Parte 1a, mas necessário para a
    # Aba Transporte pedida na Parte 2b — sem estes campos a aba não tem
    # onde persistir.
    transportadora_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("transportadoras.id"), nullable=True)
    tipo_frete: Mapped[str | None] = mapped_column(String(30), nullable=True)
    peso_liquido: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    peso_bruto: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    qtd_volumes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    especie_volumes: Mapped[str | None] = mapped_column(String(50), nullable=True)
    placa_veiculo: Mapped[str | None] = mapped_column(String(10), nullable=True)
    uf_veiculo: Mapped[str | None] = mapped_column(String(2), nullable=True)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Último ItemPedido.numero_item já usado no pedido. Itens são removidos
    # fisicamente, então max(numero_item) dos itens atuais reaproveitaria o
    # número do último removido — este contador só cresce (ver
    # venda_service.reservar_numeros_item).
    ultimo_numero_item: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    itens: Mapped[list["ItemPedido"]] = relationship(
        back_populates="pedido",
        cascade="all, delete-orphan",
        order_by="ItemPedido.numero_item",
    )
    encaixes: Mapped[list["Encaixe"]] = relationship(back_populates="pedido")  # noqa: F821
    vendedor: Mapped["Vendedor | None"] = relationship(back_populates="pedidos")  # noqa: F821
    tabela_preco: Mapped["TabelaPreco | None"] = relationship()  # noqa: F821
    cliente: Mapped["Cliente | None"] = relationship()  # noqa: F821
    transportadora: Mapped["Transportadora | None"] = relationship()  # noqa: F821
    notas_fiscais: Mapped[list["NotaFiscal"]] = relationship(back_populates="pedido")  # noqa: F821

    @property
    def cliente_codigo(self) -> str | None:
        return self.cliente.codigo if self.cliente_id and self.cliente else None


class ItemPedido(Base):
    __tablename__ = "itens_pedido"
    __table_args__ = (UniqueConstraint("pedido_id", "numero_item", name="uq_itens_pedido_pedido_numero_item"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("pedidos_venda.id"), nullable=False)
    # Número sequencial fixo do item dentro do pedido (1, 2, 3… — exibido
    # 001, 002…) para rastreio ("pedido 000001, item 003"). Nunca é
    # reaproveitado nem muda na troca de SKU; vem de
    # PedidoVenda.ultimo_numero_item.
    numero_item: Mapped[int] = mapped_column(Integer, nullable=False)
    # Nullable: itens do catálogo fiscal novo (produto_id/sku_id, ver abaixo)
    # não pertencem a um GrupoMolde — só itens legados de corte preenchem
    # este campo (ver models/pedido.py — Item pai vs. avulso no fluxo novo).
    grupo_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("grupos_molde.id"), nullable=True)
    cor: Mapped[str | None] = mapped_column(String(50))
    lote_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("lotes_tecido.id"), nullable=True)
    qtd_p: Mapped[int] = mapped_column(Integer, default=0)
    qtd_m: Mapped[int] = mapped_column(Integer, default=0)
    qtd_g: Mapped[int] = mapped_column(Integer, default=0)
    qtd_gg: Mapped[int] = mapped_column(Integer, default=0)
    qtd_g1: Mapped[int] = mapped_column(Integer, default=0)
    qtd_g2: Mapped[int] = mapped_column(Integer, default=0)
    qtd_g3: Mapped[int] = mapped_column(Integer, default=0)
    preco_unitario: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    preco_total: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    # True quando o preço foi digitado à mão na edição inline do item
    # (PATCH /{id}/itens/{item_id}); POST /{id}/aplicar-tabela sobrescreve
    # mesmo assim e volta para False.
    preco_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Produto do cadastro fiscal (NCM/CEST/unidade/peso) — opcional e
    # coexiste com grupo_id: pedidos de corte legado usam só grupo_id,
    # pedidos de venda fiscal (Fase 4/NF-e) preenchem produto_id também.
    produto_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("produtos.id"), nullable=True)
    # SKU (combinação de grade) do produto acima, quando o item vem de um
    # produto "pai" — item avulso (sem SKUs) preenche só produto_id.
    sku_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("produtos_sku.id"), nullable=True)
    # Quantidade genérica dos itens do fluxo novo (produto/SKU) — os itens
    # legados de corte usam qtd_p..qtd_g3 em vez deste campo.
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # TES do item — herda do produto (tes_saida_id) ou do cabeçalho do
    # pedido quando não informado; ver POST /{id}/itens no router.
    tes_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tes.id"), nullable=True)
    # desconto_pct (Float) é o campo antigo, mantido em sincronia com
    # desconto_percentual para quem ainda lê dele (bulk/NF-e).
    desconto_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    desconto_valor: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    desconto_percentual: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=0, server_default="0")
    desconto_tipo: Mapped[str] = mapped_column(String(10), nullable=False, default="VALOR", server_default="VALOR")
    acrescimo_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    acrescimo_valor: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Descrição editável do item (maiúscula, até 120). Preenchida com
    # descricao_completa ao criar/trocar o SKU; vazia no PATCH volta a ela.
    descricao: Mapped[str | None] = mapped_column(String(120), nullable=True)

    pedido: Mapped["PedidoVenda"] = relationship(back_populates="itens")
    grupo: Mapped["GrupoMolde | None"] = relationship()  # noqa: F821
    lote: Mapped["LoteTecido | None"] = relationship()  # noqa: F821
    produto: Mapped["Produto | None"] = relationship()  # noqa: F821
    sku: Mapped["ProdutoSKU | None"] = relationship()  # noqa: F821

    @property
    def sku_codigo(self) -> str | None:
        return self.sku.codigo if self.sku_id and self.sku else None

    @property
    def ref_codigo(self) -> str | None:
        if self.sku_id and self.sku:
            return self.sku.codigo
        if self.produto:
            return self.produto.codigo
        if self.grupo:
            return self.grupo.codigo
        return None

    @property
    def descricao_completa(self) -> str:
        if self.sku_id and self.sku:
            pai = self.sku.produto_pai
            partes = [pai.descricao if pai else "", self.sku.linha_item_descricao, self.sku.coluna_item_descricao]
            return " ".join(p for p in partes if p)
        if self.produto:
            return self.produto.descricao
        if self.grupo:
            return f"{self.grupo.nome} — {self.cor}" if self.cor else self.grupo.nome
        return ""

    @property
    def quantidade_total(self) -> int:
        if self.produto_id and not self.grupo_id:
            return self.quantidade
        return (
            (self.qtd_p or 0)
            + (self.qtd_m or 0)
            + (self.qtd_g or 0)
            + (self.qtd_gg or 0)
            + (self.qtd_g1 or 0)
            + (self.qtd_g2 or 0)
            + (self.qtd_g3 or 0)
        )


@event.listens_for(Session, "before_flush")
def _numerar_itens_sem_numero(session, flush_context, instances):
    """Rede de segurança: item novo sem numero_item (criado fora dos
    endpoints, que numeram via venda_service.reservar_numeros_item) recebe o
    próximo número do pedido, na ordem em que entrou na sessão. Mesmo
    contador do caminho normal, então nunca reaproveita número."""
    novos = [o for o in session.new if isinstance(o, ItemPedido) and o.numero_item is None]
    for item in novos:
        pedido = item.pedido
        if pedido is None and item.pedido_id is not None:
            pedido = session.get(PedidoVenda, item.pedido_id)
        if pedido is None:
            continue
        if pedido in session.new:
            # Pedido ainda não gravado: o contador vai junto no mesmo INSERT.
            pedido.ultimo_numero_item = (pedido.ultimo_numero_item or 0) + 1
            item.numero_item = pedido.ultimo_numero_item
            continue
        conn = session.connection()
        conn.execute(
            update(PedidoVenda.__table__)
            .where(PedidoVenda.__table__.c.id == pedido.id)
            .values(ultimo_numero_item=PedidoVenda.__table__.c.ultimo_numero_item + 1)
        )
        item.numero_item = conn.execute(
            select(PedidoVenda.__table__.c.ultimo_numero_item).where(PedidoVenda.__table__.c.id == pedido.id)
        ).scalar_one()
        # Mantém o objeto em memória igual ao banco sem marcá-lo como sujo.
        set_committed_value(pedido, "ultimo_numero_item", item.numero_item)
