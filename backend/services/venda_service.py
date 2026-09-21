import base64
import os
import uuid
from decimal import Decimal
from typing import Optional

from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models.pedido import ItemPedido, PedidoVenda
from models.produto import Produto
from models.venda import Empresa, PrecoReferencia, TabelaPreco

_SENHA_MASCARADA = "••••••••"


def get_produto_do_item(item: ItemPedido, db: Session) -> Optional[Produto]:
    if item.produto_id is None:
        return None
    return db.get(Produto, item.produto_id)


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
        "certificado_valido": bool(empresa.certificado_path) and os.path.exists(empresa.certificado_path),
        "nfe_serie_padrao": empresa.nfe_serie_padrao,
        "nfe_numero_atual": empresa.nfe_numero_atual,
        "nfce_serie_padrao": empresa.nfce_serie_padrao,
        "nfce_numero_atual": empresa.nfce_numero_atual,
    }


def atualizar_fiscal(db: Session, empresa: Empresa, payload: dict) -> Empresa:
    if "certificado_senha" in payload and payload["certificado_senha"] is not None:
        payload["certificado_senha"] = base64.b64encode(
            payload["certificado_senha"].encode("utf-8")
        ).decode("ascii")
    for field, val in payload.items():
        setattr(empresa, field, val)
    db.commit()
    db.refresh(empresa)
    return empresa


def testar_certificado(certificado_path: str, certificado_senha: str) -> dict:
    if not os.path.exists(certificado_path):
        return {"valido": False, "titular": None, "validade": None, "erro": "Arquivo de certificado não encontrado."}

    try:
        with open(certificado_path, "rb") as f:
            dados = f.read()
        _, certificado, _ = pkcs12.load_key_and_certificates(dados, certificado_senha.encode("utf-8"))
    except Exception:
        return {"valido": False, "titular": None, "validade": None, "erro": "Senha incorreta ou arquivo .pfx inválido."}

    if certificado is None:
        return {"valido": False, "titular": None, "validade": None, "erro": "Certificado não encontrado dentro do arquivo .pfx."}

    titular_attrs = certificado.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    titular = titular_attrs[0].value if titular_attrs else None
    validade = certificado.not_valid_after_utc if hasattr(certificado, "not_valid_after_utc") else certificado.not_valid_after

    return {
        "valido": True,
        "titular": titular,
        "validade": validade.strftime("%d/%m/%Y"),
        "erro": None,
    }


def proximo_numero(db: Session, tipo: str) -> str:
    result = db.execute(
        select(func.max(PedidoVenda.numero)).where(PedidoVenda.tipo == tipo)
    ).scalar()
    if result is None:
        candidate = "000001"
    else:
        try:
            candidate = str(int(result) + 1).zfill(6)
        except (ValueError, TypeError):
            count = db.execute(
                select(func.count(PedidoVenda.id)).where(PedidoVenda.tipo == tipo)
            ).scalar() or 0
            candidate = str(count + 1).zfill(6)

    # Garantir unicidade global (evitar colisão entre tipos)
    while db.execute(
        select(PedidoVenda.id).where(PedidoVenda.numero == candidate)
    ).scalar() is not None:
        candidate = str(int(candidate) + 1).zfill(6)

    return candidate


def get_preco(
    grupo_id: uuid.UUID,
    tabela_id: uuid.UUID,
    condicoes: str,
    db: Session,
) -> Optional[Decimal]:
    preco_ref = db.execute(
        select(PrecoReferencia).where(
            PrecoReferencia.grupo_id == grupo_id,
            PrecoReferencia.tabela_id == tabela_id,
        )
    ).scalars().first()
    if not preco_ref:
        return None
    if condicoes == "avista":
        return Decimal(str(preco_ref.preco_avista))
    return Decimal(str(preco_ref.preco_aprazo))


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


def calcular_totais(
    itens: list,
    tabela: TabelaPreco | None,
    condicoes: str,
    db: Session,
) -> tuple:
    subtotal = calcular_subtotal_itens(itens)
    comissao = subtotal * Decimal(str(tabela.comissao_pct or 0)) if tabela else Decimal("0")
    return subtotal, comissao


def recalcular_pedido(db: Session, pedido_id: uuid.UUID) -> None:
    """Recalcula total_pedido e comissao_valor do pedido.

    total_pedido = subtotal líquido dos itens (já com desconto/acréscimo
    por item) - desconto geral + acréscimo geral + frete + seguro +
    despesas. Comissão incide só sobre o subtotal dos itens, não sobre
    frete/seguro/despesas.
    """
    pedido = db.get(PedidoVenda, pedido_id)
    if not pedido:
        return
    itens = db.execute(
        select(ItemPedido).where(ItemPedido.pedido_id == pedido_id)
    ).scalars().all()

    tabela = db.get(TabelaPreco, pedido.tabela_preco_id) if pedido.tabela_preco_id else None
    subtotal, comissao = calcular_totais(itens, tabela, pedido.condicoes or "", db)

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
