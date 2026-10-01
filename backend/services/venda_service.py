import shutil
import uuid
from decimal import Decimal
from typing import Optional

from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from fastapi import HTTPException
from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import Session

from models.cliente import Cliente
from models.nfe import NotaFiscal
from models.pedido import ItemPedido, PedidoVenda
from models.produto import Produto
from models.produto_sku import ProdutoSKU
from models.venda import (
    Empresa,
    PrecoReferencia,
    PrecoTabelaProduto,
    Vendedor,
    VendedorTabelaComissao,
)
from services.pasta_dados import existe, pasta_certificados, relativo, resolver
from services.segredo_service import chave_disponivel, cifrar_segredo

_SENHA_MASCARADA = "••••••••"


def get_produto_do_item(item: ItemPedido, db: Session) -> Optional[Produto]:
    if item.produto_id is None:
        return None
    return db.get(Produto, item.produto_id)


# ── Cópia do cliente no pedido (cliente_*) ────────────────────────────────────
# Coluna do pedido → como ler do Cliente. Documento: CNPJ ou, se não tiver,
# CPF (NF-e decide pela contagem de dígitos); telefone: fixo ou celular.
SNAPSHOT_CLIENTE = {
    "cliente_razao_social": lambda c: c.razao_social,
    "cliente_cnpj": lambda c: c.cnpj or c.cpf,
    "cliente_ie": lambda c: c.ie,
    "cliente_endereco": lambda c: c.endereco,
    "cliente_numero": lambda c: c.numero,
    "cliente_bairro": lambda c: c.bairro,
    "cliente_cidade": lambda c: c.cidade,
    "cliente_uf": lambda c: c.estado,
    "cliente_cep": lambda c: c.cep,
    "cliente_codigo_ibge_municipio": lambda c: c.codigo_ibge_municipio,
    "cliente_codigo_pais": lambda c: c.codigo_pais or "1058",
    "cliente_telefone": lambda c: c.telefone or c.celular,
    "cliente_email": lambda c: c.email or c.email_nfe,
}

# Pedido cuja cópia ainda pode acompanhar o cadastro: Aberto e sem NF-e
# (nfe_id nem nota em notas_fiscais). Fechado/Cancelado/com NF-e fica
# como foi emitido.
_TEM_NFE = exists().where(NotaFiscal.pedido_id == PedidoVenda.id)
_FILTRO_SINCRONIZAVEL = (
    PedidoVenda.status == "Aberto",
    PedidoVenda.nfe_id.is_(None),
    ~_TEM_NFE,
)


def aplicar_snapshot_cliente(pedido: PedidoVenda, cliente: Cliente) -> None:
    """Liga o pedido ao cliente e copia o cadastro para os campos cliente_*
    (lidos por PDF, NF-e, portal e relatórios). Não confere status — quem
    chama decide (criação, troca de cliente, sincronizar_cliente_pedidos)."""
    pedido.cliente_id = cliente.id
    for campo, ler in SNAPSHOT_CLIENTE.items():
        setattr(pedido, campo, ler(cliente))


def pedido_sincronizavel(db: Session, pedido: PedidoVenda) -> bool:
    if pedido.status != "Aberto" or pedido.nfe_id is not None:
        return False
    return not db.execute(select(NotaFiscal.id).where(NotaFiscal.pedido_id == pedido.id).limit(1)).first()


def sincronizar_cliente_pedidos(db: Session, cliente_id: int) -> int:
    """Recopia o cadastro do cliente para os pedidos dele que ainda podem
    mudar (Aberto, sem NF-e). Não faz commit — roda na transação de quem
    chama. Retorna quantos pedidos foram atualizados."""
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        return 0
    pedidos = (
        db.execute(select(PedidoVenda).where(PedidoVenda.cliente_id == cliente_id, *_FILTRO_SINCRONIZAVEL))
        .scalars()
        .all()
    )
    for pedido in pedidos:
        aplicar_snapshot_cliente(pedido, cliente)
    return len(pedidos)


def get_ou_criar_empresa(db: Session) -> Empresa:
    empresa = db.execute(select(Empresa)).scalars().first()
    if empresa is None:
        empresa = Empresa()
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
    return empresa


def empresa_fiscal_out(empresa: Empresa) -> dict:
    return {
        "regime_tributario": empresa.regime_tributario,
        "uf_emitente": empresa.uf_emitente,
        "ambiente_sefaz": empresa.ambiente_sefaz,
        "certificado_path": empresa.certificado_path,
        "certificado_senha": _SENHA_MASCARADA if empresa.certificado_senha else None,
        "certificado_valido": existe(empresa.certificado_path),
        "nfe_serie_padrao": empresa.nfe_serie_padrao,
        "nfe_numero_atual": empresa.nfe_numero_atual,
        "nfce_serie_padrao": empresa.nfce_serie_padrao,
        "nfce_numero_atual": empresa.nfce_numero_atual,
    }


def atualizar_fiscal(db: Session, empresa: Empresa, payload: dict) -> Empresa:
    # Item 4.2: a senha do certificado NUNCA vai para o banco em texto claro
    # nem em base64 reversível — vai cifrada (envelope AES-GCM `enc:v1:...`)
    # com a chave mestre/do desktop. Sem chave, recusa salvar com mensagem
    # clara (leia os trade-offs no README).
    if "certificado_senha" in payload and payload["certificado_senha"] is not None:
        senha = str(payload["certificado_senha"]).strip()
        if senha:
            if not senha.startswith("enc:v1:"):  # já-cifrado: passa direto
                if not chave_disponivel():
                    raise HTTPException(
                        status_code=400,
                        detail="Sem chave de segurança configurada para armazenar a senha do "
                        "certificado. No desktop abra pelo SmartCut; fora dele defina "
                        "CERT_SENHA_KEY no ambiente (ver README).",
                    )
                payload["certificado_senha"] = cifrar_segredo(senha)
    if payload.get("certificado_path"):
        payload["certificado_path"] = _guardar_certificado(payload["certificado_path"])
    for field, val in payload.items():
        setattr(empresa, field, val)
    db.commit()
    db.refresh(empresa)
    return empresa


def _guardar_certificado(caminho: str) -> str:
    """Copia o .pfx escolhido para a pasta de certificados (dentro da pasta
    de dados do usuário no app instalado) e devolve o caminho a gravar.

    O arquivo escolhido no diálogo pode estar em qualquer lugar (Downloads,
    pendrive...) — a cópia garante que o certificado continue disponível e
    entre no backup da pasta de dados. Já dentro da pasta: só normaliza.
    """
    origem = resolver(caminho)
    if not origem.is_file():
        return caminho  # inexistente: grava como veio (a tela mostra inválido)
    pasta = pasta_certificados()
    destino = pasta / origem.name
    if origem.resolve() != destino.resolve():
        pasta.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, destino)
    return relativo(destino)


def testar_certificado(certificado_path: str, certificado_senha: str) -> dict:
    arquivo_pfx = resolver(certificado_path)
    if not arquivo_pfx or not arquivo_pfx.is_file():
        return {"valido": False, "titular": None, "validade": None, "erro": "Arquivo de certificado não encontrado."}

    try:
        with open(arquivo_pfx, "rb") as f:
            dados = f.read()
        _, certificado, _ = pkcs12.load_key_and_certificates(dados, certificado_senha.encode("utf-8"))
    except Exception:
        return {"valido": False, "titular": None, "validade": None, "erro": "Senha incorreta ou arquivo .pfx inválido."}

    if certificado is None:
        return {
            "valido": False,
            "titular": None,
            "validade": None,
            "erro": "Certificado não encontrado dentro do arquivo .pfx.",
        }

    titular_attrs = certificado.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    titular = titular_attrs[0].value if titular_attrs else None
    validade = (
        certificado.not_valid_after_utc if hasattr(certificado, "not_valid_after_utc") else certificado.not_valid_after
    )

    return {
        "valido": True,
        "titular": titular,
        "validade": validade.strftime("%d/%m/%Y"),
        "erro": None,
    }


def proximo_numero(db: Session, tipo: str) -> str:
    result = db.execute(select(func.max(PedidoVenda.numero)).where(PedidoVenda.tipo == tipo)).scalar()
    if result is None:
        candidate = "000001"
    else:
        try:
            candidate = str(int(result) + 1).zfill(6)
        except (ValueError, TypeError):
            count = db.execute(select(func.count(PedidoVenda.id)).where(PedidoVenda.tipo == tipo)).scalar() or 0
            candidate = str(count + 1).zfill(6)

    # Garantir unicidade global (evitar colisão entre tipos)
    while db.execute(select(PedidoVenda.id).where(PedidoVenda.numero == candidate)).scalar() is not None:
        candidate = str(int(candidate) + 1).zfill(6)

    return candidate


def get_preco(
    grupo_id: uuid.UUID,
    tabela_id: uuid.UUID,
    condicoes: str,
    db: Session,
) -> Optional[Decimal]:
    preco_ref = (
        db.execute(
            select(PrecoReferencia).where(
                PrecoReferencia.grupo_id == grupo_id,
                PrecoReferencia.tabela_id == tabela_id,
            )
        )
        .scalars()
        .first()
    )
    if not preco_ref:
        return None
    if condicoes == "avista":
        return Decimal(str(preco_ref.preco_avista))
    return Decimal(str(preco_ref.preco_aprazo))


def _preco_por_condicao(registro, condicoes: str) -> Decimal:
    # Mesma escolha de get_preco: "avista" → à vista; qualquer outra coisa
    # (inclusive vazio) → a prazo.
    if condicoes == "avista":
        return Decimal(str(registro.preco_avista))
    return Decimal(str(registro.preco_aprazo))


def resolver_preco_item(
    db: Session,
    sku: Optional[ProdutoSKU],
    tabela_preco_id: Optional[uuid.UUID],
    condicoes: str,
    produto: Optional[Produto] = None,
    grupo_id: Optional[uuid.UUID] = None,
) -> tuple[Optional[Decimal], Optional[str]]:
    """Preço unitário de um item de pedido e a origem dele.

    sku: SKU do item (None para produto avulso ou item legado de corte).
    produto: produto do item — se omitido e houver sku, usa o pai do SKU.
    grupo_id: GrupoMolde do item legado de corte (PrecoReferencia).

    Prioridade:
      1. "TABELA_SKU"     — preço do SKU na tabela (precos_tabela_produto)
      2. "TABELA_PRODUTO" — preço do produto pai na tabela
      3. "TABELA_GRUPO"   — PrecoReferencia do grupo (itens legados)
      4. "SKU"/"PRODUTO"  — regra fora de tabela: preço manual do SKU >
                            preço de venda do produto (ver
                            produto_service.grade_pedido)
      5. (None, None)     — sem preço
    """
    if produto is None and sku is not None:
        produto = sku.produto_pai or db.get(Produto, sku.produto_pai_id)

    if tabela_preco_id:
        if sku is not None:
            registro = (
                db.execute(
                    select(PrecoTabelaProduto).where(
                        PrecoTabelaProduto.tabela_preco_id == tabela_preco_id,
                        PrecoTabelaProduto.sku_id == sku.id,
                    )
                )
                .scalars()
                .first()
            )
            if registro:
                return _preco_por_condicao(registro, condicoes), "TABELA_SKU"
        if produto is not None:
            registro = (
                db.execute(
                    select(PrecoTabelaProduto).where(
                        PrecoTabelaProduto.tabela_preco_id == tabela_preco_id,
                        PrecoTabelaProduto.produto_id == produto.id,
                    )
                )
                .scalars()
                .first()
            )
            if registro:
                return _preco_por_condicao(registro, condicoes), "TABELA_PRODUTO"
        if grupo_id is not None:
            preco = get_preco(grupo_id, tabela_preco_id, condicoes, db)
            if preco is not None:
                return preco, "TABELA_GRUPO"

    if sku is not None and sku.preco_manual and sku.preco_venda is not None:
        return Decimal(str(sku.preco_venda)), "SKU"
    if produto is not None and produto.preco_venda and produto.preco_venda > 0:
        return Decimal(str(produto.preco_venda)), "PRODUTO"
    return None, None


def calcular_subtotal_itens(itens: list) -> Decimal:
    """Soma líquida dos itens: preco_total (bruto) - desconto + acréscimo
    de cada item. Comissão incide sobre este valor (mercadoria, sem frete/
    seguro/despesas)."""
    subtotal = Decimal("0")
    for item in itens:
        bruto = Decimal(str(item.preco_total or 0))
        desconto = Decimal(str(item.desconto_valor or 0))
        acrescimo = Decimal(str(item.acrescimo_valor or 0))
        subtotal += bruto - desconto + acrescimo
    return subtotal


def resolver_comissao(
    db: Session,
    vendedor_id: Optional[uuid.UUID],
    tabela_preco_id: Optional[uuid.UUID],
) -> tuple[Decimal, str]:
    """% de comissão (0–100) do par vendedor + tabela e a origem dele.

    Prioridade:
      1. "SEM_VENDEDOR"    — pedido sem vendedor → 0
      2. "VINCULO"         — VendedorTabelaComissao do par (pulado sem tabela)
      3. "PADRAO_VENDEDOR" — Vendedor.comissao_padrao_pct
      4. "NENHUMA"         — nada configurado → 0

    TabelaPreco.comissao_pct é legado e nunca é lido aqui.
    """
    if vendedor_id is None:
        return Decimal("0"), "SEM_VENDEDOR"

    if tabela_preco_id is not None:
        vinculo = (
            db.execute(
                select(VendedorTabelaComissao).where(
                    VendedorTabelaComissao.vendedor_id == vendedor_id,
                    VendedorTabelaComissao.tabela_preco_id == tabela_preco_id,
                )
            )
            .scalars()
            .first()
        )
        if vinculo is not None:
            return Decimal(str(vinculo.comissao_pct)), "VINCULO"

    vendedor = db.get(Vendedor, vendedor_id)
    if vendedor is not None and vendedor.comissao_padrao_pct is not None:
        return Decimal(str(vendedor.comissao_padrao_pct)), "PADRAO_VENDEDOR"

    return Decimal("0"), "NENHUMA"


def aplicar_comissao(db: Session, pedido: PedidoVenda) -> None:
    """Grava no pedido o snapshot de comissao_pct/comissao_origem. Quem chama
    decide quando (criação, troca de vendedor/tabela com pedido Aberto) —
    recalcular_pedido só reaproveita o snapshot."""
    pedido.comissao_pct, pedido.comissao_origem = resolver_comissao(
        db,
        pedido.vendedor_id,
        pedido.tabela_preco_id,
    )


def calcular_totais(itens: list, comissao_pct) -> tuple:
    subtotal = calcular_subtotal_itens(itens)
    comissao = subtotal * Decimal(str(comissao_pct or 0)) / 100
    return subtotal, comissao


def recalcular_pedido(db: Session, pedido_id: uuid.UUID) -> None:
    """Recalcula total_pedido e comissao_valor do pedido.

    total_pedido = subtotal líquido dos itens (já com desconto/acréscimo
    por item) - desconto geral + acréscimo geral + frete + seguro +
    despesas. Comissão = subtotal dos itens × pedido.comissao_pct (snapshot,
    ver aplicar_comissao) — não incide sobre frete/seguro/despesas.
    """
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        return
    itens = db.execute(select(ItemPedido).where(ItemPedido.pedido_id == pedido_id)).scalars().all()

    subtotal, comissao = calcular_totais(itens, pedido.comissao_pct)

    total = (
        subtotal
        - Decimal(str(pedido.desconto_geral_valor or 0))
        + Decimal(str(pedido.acrescimo_valor or 0))
        + Decimal(str(pedido.valor_frete or 0))
        + Decimal(str(pedido.valor_seguro or 0))
        + Decimal(str(pedido.valor_despesas or 0))
    )

    pedido.total_pedido = total
    pedido.comissao_valor = comissao


def reservar_numeros_item(db: Session, pedido_id: uuid.UUID, quantidade: int = 1) -> int:
    """Reserva `quantidade` números de item seguidos para o pedido e devolve
    o primeiro. UPDATE atômico no contador PedidoVenda.ultimo_numero_item
    (trava a linha no Postgres; no SQLite a escrita já é serializada) — dois
    requests simultâneos nunca pegam o mesmo número. O contador só cresce:
    número de item removido não volta.

    O objeto PedidoVenda em memória é sincronizado (synchronize_session)."""
    db.execute(
        update(PedidoVenda)
        .where(PedidoVenda.id == pedido_id)
        .values(ultimo_numero_item=PedidoVenda.ultimo_numero_item + quantidade)
        .execution_options(synchronize_session="fetch")
    )
    ultimo = db.execute(select(PedidoVenda.ultimo_numero_item).where(PedidoVenda.id == pedido_id)).scalar_one()
    return ultimo - quantidade + 1


def _dec(v) -> Decimal:
    return Decimal(str(v or 0))


def resumo_totais(pedido, itens) -> dict:
    """Totais do pedido para o cabeçalho da tela (resposta do detalhe/PUT).

    qtd_total           soma das quantidades (grade qtd_p..g3 no item de corte)
    valor_mercadoria    soma de qtd × preço, sem desconto (preco_total bruto)
    desconto_itens_total soma dos descontos em R$ dos itens
    valor_total         total do pedido gravado (ver recalcular_pedido)

    Aceita models ou schemas de saída — só lê atributos."""
    centavos = Decimal("0.01")
    return {
        "qtd_total": sum(int(i.quantidade_total or 0) for i in itens),
        "valor_mercadoria": sum((_dec(i.preco_total) for i in itens), Decimal("0")).quantize(centavos),
        "desconto_itens_total": sum((_dec(i.desconto_valor) for i in itens), Decimal("0")).quantize(centavos),
        "desconto_geral_valor": _dec(pedido.desconto_geral_valor).quantize(centavos),
        "desconto_geral_pct": _dec(pedido.desconto_geral_pct),
        "valor_total": _dec(pedido.total_pedido).quantize(centavos),
        "comissao_pct": _dec(pedido.comissao_pct),
        "comissao_valor": _dec(pedido.comissao_valor).quantize(centavos),
    }
