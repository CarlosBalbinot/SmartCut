"""Fonte de dados do relVen001 (Pedido de venda).

Monta o contexto do modelo Jinja2 só com tipos simples (dict/list/str/
Decimal/date) — o modelo roda em sandbox e não recebe objetos do ORM.

Chaves: empresa, pedido, cliente, itens, totais, parcelas (a engine
acrescenta "impressao"). Valores em Decimal/date crus: a formatação é dos
filtros do modelo (moeda, numero, data, cnpj_cpf, cep, telefone).
"""

from __future__ import annotations

import logging
import uuid
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from config import settings
from models.condicao_pagamento import CondicaoPagamento
from models.pedido import ItemPedido, PedidoVenda
from models.produto_sku import ProdutoSKU
from services.condicao_service import gerar_parcelas
from services.nfe_service import _MODFRETE_POR_TIPO
from services.venda_service import get_ou_criar_empresa

logger = logging.getLogger(__name__)

_CENTAVOS = Decimal("0.01")

# Título do documento impresso pelo status (igual ao ERP).
_TITULO_POR_STATUS = {"Aberto": "ORÇAMENTO", "Fechado": "VENDA", "Cancelado": "CANCELADO"}

# modFrete da NF-e (mesmo mapeamento da emissão — nfe_service).
_DESCRICAO_MODFRETE = {
    "0": "Contratação do Frete por conta do Remetente (CIF)",
    "1": "Contratação do Frete por conta do Destinatário (FOB)",
    "2": "Contratação do Frete por conta de Terceiros",
    "3": "Transporte Próprio por conta do Remetente",
    "4": "Transporte Próprio por conta do Destinatário",
    "9": "Sem Ocorrência de Transporte",
}

_UM_PADRAO = "PC"

_OPTS = [
    selectinload(PedidoVenda.cliente),
    selectinload(PedidoVenda.vendedor),
    selectinload(PedidoVenda.tabela_preco),
    selectinload(PedidoVenda.itens).selectinload(ItemPedido.grupo),
    selectinload(PedidoVenda.itens).selectinload(ItemPedido.produto),
    selectinload(PedidoVenda.itens).selectinload(ItemPedido.sku).selectinload(ProdutoSKU.produto_pai),
    selectinload(PedidoVenda.itens).selectinload(ItemPedido.sku).selectinload(ProdutoSKU.linha_item),
    selectinload(PedidoVenda.itens).selectinload(ItemPedido.sku).selectinload(ProdutoSKU.coluna_item),
]


def _dec(valor) -> Decimal:
    return Decimal(str(valor or 0))


def _txt(valor) -> str:
    return str(valor or "").strip()


# Campos do cabeçalho (chave do contexto → nome na tela Configurações).
_CAMPOS_EMPRESA = {
    "nome": "Razão social",
    "endereco": "Endereço",
    "numero": "Número",
    "bairro": "Bairro",
    "cidade": "Cidade",
    "uf": "UF",
    "cep": "CEP",
    "cnpj": "CNPJ",
    "ie": "Inscrição estadual",
    "telefone": "Telefone",
    "email": "E-mail",
    "logo": "Logo",
}


def _arquivo_logo(logo_path: str | None) -> Path | None:
    """Mesma resolução do GET /configuracao-empresa/logo: o upload grava
    "uploads/logos/empresa_logo.png" (relativo), resolvido pelo UPLOAD_DIR —
    no Electron empacotado o cwd/uploads ficam no userData, não na pasta
    do backend."""
    if not logo_path:
        return None
    logo = str(logo_path).replace("\\", "/")
    if "uploads/" in logo:
        return Path(settings.upload_dir).resolve() / logo.split("uploads/", 1)[-1]
    return Path(logo).resolve()


def _empresa(db: Session) -> dict:
    # Import tardio: engine importa este módulo (evita ciclo no import).
    from services.relatorios.engine import arquivo_data_uri

    e = get_ou_criar_empresa(db)
    arquivo_logo = _arquivo_logo(e.logo_path)
    dados = {
        "nome": _txt(e.razao_social),
        "endereco": _txt(e.endereco),
        "numero": _txt(e.endereco_numero),
        "complemento": "",  # sem campo no cadastro da empresa
        "bairro": _txt(e.endereco_bairro),
        "cidade": _txt(e.cidade),
        "uf": _txt(e.uf_emitente),
        "cep": _txt(e.cep),
        "cnpj": _txt(e.cnpj),
        "ie": _txt(e.ie),
        "telefone": _txt(e.telefone1 or e.telefone2),
        "email": _txt(e.email),
        # Logo das configurações da empresa embutido (data URI; "" sem
        # logo): o PDF do Electron é gerado de um arquivo temporário, então
        # a imagem não pode ser URL/caminho relativo.
        "logo": arquivo_data_uri(arquivo_logo) if arquivo_logo else "",
    }
    # Vazios no cadastro: o modelo avisa (só na tela) para preencher em
    # Configurações > Empresa.
    dados["faltando"] = [rotulo for chave, rotulo in _CAMPOS_EMPRESA.items() if not dados[chave]]
    if dados["faltando"]:
        logger.info("[relatorios] empresa sem: %s", ", ".join(dados["faltando"]))
    return dados


def _tipo_frete(tipo: str | None) -> dict:
    codigo = _MODFRETE_POR_TIPO.get(tipo, "9") if tipo else "9"
    return {"codigo": codigo, "descricao": _DESCRICAO_MODFRETE[codigo], "nome": _txt(tipo)}


def _cliente(pedido: PedidoVenda) -> dict:
    # Cópia cliente_* gravada no pedido. Complemento não tem cópia no
    # pedido: vem do cadastro vinculado, quando houver.
    cad = pedido.cliente
    return {
        "codigo": _txt(pedido.cliente_codigo),
        "nome": _txt(pedido.cliente_razao_social),
        "cpf_cnpj": _txt(pedido.cliente_cnpj),
        "ie": _txt(pedido.cliente_ie),
        "endereco": _txt(pedido.cliente_endereco),
        "numero": _txt(pedido.cliente_numero),
        "complemento": _txt(cad.complemento if cad else ""),
        "bairro": _txt(pedido.cliente_bairro),
        "cidade": _txt(pedido.cliente_cidade),
        "uf": _txt(pedido.cliente_uf),
        "cep": _txt(pedido.cliente_cep),
        "telefone": _txt(pedido.cliente_telefone),
        "email": _txt(pedido.cliente_email),
    }


def _unidade(item: ItemPedido) -> str:
    produto = item.sku.produto_pai if item.sku_id and item.sku else item.produto
    return _txt(getattr(produto, "unidade", None)) or _UM_PADRAO


def _item(item: ItemPedido) -> dict:
    quantidade = int(item.quantidade_total or 0)
    bruto = _dec(item.preco_total)
    desconto = _dec(item.desconto_valor)
    # Mesma conta de calcular_subtotal_itens (bruto - desconto + acréscimo).
    total = bruto - desconto + _dec(item.acrescimo_valor)
    valor_un = (total / quantidade).quantize(_CENTAVOS, ROUND_HALF_UP) if quantidade else _dec(item.preco_unitario)
    return {
        "numero_item": item.numero_item,
        "codigo": _txt(item.ref_codigo),
        "descricao": _txt(item.descricao) or item.descricao_completa,
        "quantidade": quantidade,
        "um": _unidade(item),
        "valor_base": _dec(item.preco_unitario),
        "desconto_pct": _dec(item.desconto_percentual),
        "desconto_valor": desconto,
        "valor_un": valor_un,
        "valor_total": total.quantize(_CENTAVOS, ROUND_HALF_UP),
    }


def _totais(pedido: PedidoVenda, itens: list[dict], originais: list[ItemPedido]) -> dict:
    """subtotal - desconto + frete + despesas = valor_total (total gravado,
    ver venda_service.recalcular_pedido). "despesas" junta o que não é
    mercadoria/desconto/frete: seguro, despesas e acréscimos."""
    subtotal = sum((_dec(i.preco_total) for i in originais), Decimal("0"))
    desconto = sum((i["desconto_valor"] for i in itens), Decimal("0")) + _dec(pedido.desconto_geral_valor)
    despesas = (
        _dec(pedido.valor_seguro)
        + _dec(pedido.valor_despesas)
        + _dec(pedido.acrescimo_valor)
        + sum((_dec(i.acrescimo_valor) for i in originais), Decimal("0"))
    )
    return {
        "subtotal": subtotal.quantize(_CENTAVOS),
        "desconto": desconto.quantize(_CENTAVOS),
        "frete": _dec(pedido.valor_frete).quantize(_CENTAVOS),
        "despesas": despesas.quantize(_CENTAVOS),
        "valor_total": _dec(pedido.total_pedido).quantize(_CENTAVOS),
        "qtd_itens": len(itens),  # linhas do pedido
        "qtd_total": sum((i["quantidade"] for i in itens), 0),  # peças
    }


def _parcelas(db: Session, pedido: PedidoVenda) -> tuple[str, list[dict]]:
    """(descrição da condição, parcelas) — mesmo cálculo da prévia do pedido
    (condicao_service.gerar_parcelas)."""
    if pedido.condicao_pagamento_id is None:
        return "", []
    condicao = db.get(CondicaoPagamento, pedido.condicao_pagamento_id)
    if condicao is None:
        return "", []
    total = _dec(pedido.total_pedido)
    if total <= 0:
        return condicao.descricao, []
    try:
        lista = gerar_parcelas(condicao, total, pedido.data_emissao, pedido.primeiro_vencimento)
    except ValueError:
        return condicao.descricao, []
    return condicao.descricao, [
        {
            "documento": f"{pedido.numero}-{p['parcela']}/{p['total']}",
            "parcela": p["parcela"],
            "total_parcelas": p["total"],
            "vencimento": p["vencimento"],
            "valor": p["valor"],
        }
        for p in lista
    ]


def montar(db: Session, id_registro: str) -> dict:
    """Contexto do relVen001 para o pedido `id_registro` (UUID)."""
    try:
        pedido_id = uuid.UUID(str(id_registro))
    except ValueError:
        raise HTTPException(status_code=422, detail="id do pedido inválido.")
    pedido = db.execute(select(PedidoVenda).where(PedidoVenda.id == pedido_id).options(*_OPTS)).scalars().first()
    if pedido is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    # Relacionamento já ordenado por numero_item; o sort garante a ordem.
    originais = sorted(pedido.itens, key=lambda i: i.numero_item or 0)
    itens = [_item(i) for i in originais]
    condicao, parcelas = _parcelas(db, pedido)
    emissao = pedido.data_emissao

    return {
        "empresa": _empresa(db),
        "pedido": {
            "numero": pedido.numero,
            "emissao": emissao,
            "prazo_entrega_dias": int(pedido.prazo_entrega_dias or 0),
            "status": pedido.status,
            "titulo": _TITULO_POR_STATUS.get(pedido.status, _txt(pedido.status).upper()),
            "vendedor": _txt(pedido.vendedor.nome if pedido.vendedor else pedido.representante),
            "condicao_pagamento": _txt(condicao),
            "tipo_frete": _tipo_frete(pedido.tipo_frete),
            "observacoes": _txt(pedido.informacoes_adicionais),
            "observacoes_internas": _txt(pedido.observacoes_internas),
            "tabela_preco": _txt(pedido.tabela_preco.nome if pedido.tabela_preco else ""),
        },
        "cliente": _cliente(pedido),
        "itens": itens,
        "totais": _totais(pedido, itens, originais),
        "parcelas": parcelas,
    }
