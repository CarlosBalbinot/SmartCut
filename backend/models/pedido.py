import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

STATUS_VALIDOS = ("Aberto", "Fechado", "Cancelado")

INDICADOR_PRESENCA_VALIDOS = ("Presencial", "Internet", "Teleatendimento", "Outros")

TIPO_FRETE_VALIDOS = (
    "Sem Frete", "CIF", "FOB", "Por conta de terceiros", "Próprio", "Sem Ocorrência",
)


class PedidoVenda(Base):
    __tablename__ = "pedidos_venda"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="venda")
    data_emissao: Mapped[date] = mapped_column(Date, nullable=False)
    prazo_entrega_dias: Mapped[int | None] = mapped_column(Integer, default=20)
    condicoes: Mapped[str | None] = mapped_column(String(20))
    vendedor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("vendedores.id"), nullable=True
    )
    tabela_preco_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tabelas_preco.id"), nullable=True
    )
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
    transportadora_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("transportadoras.id"), nullable=True
    )
    tipo_frete: Mapped[str | None] = mapped_column(String(30), nullable=True)
    peso_liquido: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    peso_bruto: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    qtd_volumes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    especie_volumes: Mapped[str | None] = mapped_column(String(50), nullable=True)
    placa_veiculo: Mapped[str | None] = mapped_column(String(10), nullable=True)
    uf_veiculo: Mapped[str | None] = mapped_column(String(2), nullable=True)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    itens: Mapped[list["ItemPedido"]] = relationship(back_populates="pedido", cascade="all, delete-orphan")
    encaixes: Mapped[list["Encaixe"]] = relationship(back_populates="pedido")  # noqa: F821
    vendedor: Mapped["Vendedor | None"] = relationship(back_populates="pedidos")  # noqa: F821
    tabela_preco: Mapped["TabelaPreco | None"] = relationship()  # noqa: F821
    transportadora: Mapped["Transportadora | None"] = relationship()  # noqa: F821
    notas_fiscais: Mapped[list["NotaFiscal"]] = relationship(back_populates="pedido")  # noqa: F821


class ItemPedido(Base):
    __tablename__ = "itens_pedido"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedidos_venda.id"), nullable=False
    )
    grupo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("grupos_molde.id"), nullable=False
    )
    cor: Mapped[str | None] = mapped_column(String(50))
    lote_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lotes_tecido.id"), nullable=True
    )
    qtd_p: Mapped[int] = mapped_column(Integer, default=0)
    qtd_m: Mapped[int] = mapped_column(Integer, default=0)
    qtd_g: Mapped[int] = mapped_column(Integer, default=0)
    qtd_gg: Mapped[int] = mapped_column(Integer, default=0)
    qtd_g1: Mapped[int] = mapped_column(Integer, default=0)
    qtd_g2: Mapped[int] = mapped_column(Integer, default=0)
    qtd_g3: Mapped[int] = mapped_column(Integer, default=0)
    preco_unitario: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    preco_total: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    # Produto do cadastro fiscal (NCM/CEST/unidade/peso) — opcional e
    # coexiste com grupo_id: pedidos de corte legado usam só grupo_id,
    # pedidos de venda fiscal (Fase 4/NF-e) preenchem produto_id também.
    produto_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("produtos.id"), nullable=True
    )

    # TES do item — herda do produto (tes_saida_id) ou do cabeçalho do
    # pedido quando não informado; ver POST /{id}/itens no router.
    tes_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tes.id"), nullable=True)
    desconto_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    desconto_valor: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    acrescimo_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    acrescimo_valor: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    pedido: Mapped["PedidoVenda"] = relationship(back_populates="itens")
    grupo: Mapped["GrupoMolde"] = relationship()  # noqa: F821
    lote: Mapped["LoteTecido | None"] = relationship()  # noqa: F821
    produto: Mapped["Produto | None"] = relationship()  # noqa: F821
