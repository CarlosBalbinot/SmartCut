"""Montagem de cenários dos testes de concorrência: pedidos e OCs prontas
num status, no banco em arquivo (cada função abre e fecha a sua sessão)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from models.encaixe import Encaixe
from models.pedido import ItemPedido, PedidoVenda
from services import ordem_corte_service as svc
from tests.test_ordem_corte_producao import CAMADAS, PESO_ENCAIXE, _novo_lote, _novo_produto

# Caminho de cada status a partir do RASCUNHO com encaixe.
_CAMINHO = {
    "RASCUNHO": [],
    "ENVIADA": ["enviar"],
    "EM_CORTE": ["enviar", "iniciar"],
    "CONCLUIDA": ["enviar", "iniciar", "concluir"],
}


def pedidos(fabrica, n: int, produto_id=None, sku_id=None) -> list[uuid.UUID]:
    """`n` pedidos, cada um com um item de produto (o mínimo para gerar OC)."""
    db = fabrica()
    try:
        if produto_id is None:
            produto, sku = _novo_produto(db)
            produto_id, sku_id = produto.id, sku.id
        ids = []
        for _ in range(n):
            pedido = PedidoVenda(numero=f"P{uuid.uuid4().hex[:8]}", data_emissao=date(2026, 10, 1))
            db.add(pedido)
            db.flush()
            db.add(
                ItemPedido(
                    pedido_id=pedido.id,
                    produto_id=produto_id,
                    sku_id=sku_id,
                    cor="Azul",
                    quantidade=4,
                    preco_unitario=Decimal("90.00"),
                    preco_total=Decimal("360.00"),
                )
            )
            ids.append(pedido.id)
        db.commit()
        return ids
    finally:
        db.close()


def ocs(fabrica, n: int, status: str) -> tuple[list[uuid.UUID], uuid.UUID]:
    """`n` OCs no `status` pedido, todas usando o mesmo lote, com um encaixe
    de PESO_ENCAIXE kg × CAMADAS camadas cada. Devolve (ids das OCs, lote)."""
    db = fabrica()
    try:
        produto, sku = _novo_produto(db)
        produto_id, sku_id = produto.id, sku.id
        lote_id = _novo_lote(db).id
    finally:
        db.close()
    ids_pedidos = pedidos(fabrica, n, produto_id, sku_id)

    ids = []
    db = fabrica()
    try:
        for pedido_id in ids_pedidos:
            oc_id = uuid.UUID(str(svc.criar_ordem_corte(db, pedido_id)["id"]))
            svc.definir_tecidos(db, oc_id, [{"produto_pai_id": produto_id, "cor": "Azul", "lote_id": lote_id}])
            db.add(
                Encaixe(
                    pedido_id=pedido_id,
                    ordem_corte_id=oc_id,
                    lote_id=lote_id,
                    comp_metros=Decimal("2.000"),
                    peso_kg=PESO_ENCAIXE,
                    num_camadas=CAMADAS,
                    status="ativo",
                )
            )
            db.commit()
            for passo in _CAMINHO[status]:
                if passo == "enviar":
                    svc.enviar_a_producao(db, oc_id)
                elif passo == "iniciar":
                    svc.iniciar_corte(db, oc_id, "ANA")
                else:
                    svc.concluir(db, oc_id, "ANA", [])
            ids.append(oc_id)
        return ids, lote_id
    finally:
        db.close()
