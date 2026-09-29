"""Salvar itens do pedido em lote: PUT /{id}/itens e PUT /{id} com "itens".

Transação única (tudo ou nada), erros por item/campo em {"erros": [...]},
409 fora de Aberto e o PATCH de item individual continuando igual.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import sessionmaker

from models.pedido import ItemPedido, PedidoVenda
from models.produto import GrupoProduto, Produto
from models.produto_sku import ProdutoSKU
from tests.test_pedidos_precificacao import _criar_pedido


@pytest.fixture()
def override_get_db(engine):
    # Igual ao SessionLocal do app (autoflush=False) — o lote depende dos
    # flush explícitos, então testa com a mesma configuração de produção.
    Session = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    def _get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    return _get_db


@pytest.fixture()
def skus(db_session):
    g = GrupoProduto(codigo="G01", nome="GRUPO TESTE", prefixo="GT")
    db_session.add(g)
    db_session.commit()
    p = Produto(
        grupo_id=g.id,
        codigo="P001",
        descricao="CAMISETA",
        unidade="UN",
        preco_venda=Decimal("80.00"),
        ncm="61091000",
        origem=0,
    )
    db_session.add(p)
    db_session.commit()
    m = ProdutoSKU(produto_pai_id=p.id, codigo="P001-M", preco_venda=Decimal("90.00"), preco_manual=True)
    g_ = ProdutoSKU(produto_pai_id=p.id, codigo="P001-G")
    db_session.add_all([m, g_])
    db_session.commit()
    return m, g_


def _url(pedido, sufixo=""):
    return f"/api/v1/pedidos-venda/{pedido['id']}{sufixo}"


def _itens_no_banco(db_session, pedido):
    db_session.expire_all()
    return db_session.query(ItemPedido).filter(ItemPedido.pedido_id == uuid.UUID(pedido["id"])).all()


class TestLoteItens:
    def test_cria_atualiza_remove_numa_transacao(self, client, headers_admin, db_session, cliente, skus):
        m, g = skus
        pedido = _criar_pedido(client, headers_admin, cliente)
        res = client.put(
            _url(pedido, "/itens"),
            headers=headers_admin,
            json={
                "criar": [
                    {"ref_temp": "n1", "sku_id": m.id, "quantidade": 2},
                    {"ref_temp": "n2", "sku_codigo": "p001-g", "quantidade": 1, "desconto_percentual": "10"},
                ]
            },
        )
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        por_sku = {i["sku_codigo"]: i for i in data["itens"]}
        # M: preço manual do SKU (90); G: preço do pai (80) com 10%.
        assert Decimal(por_sku["P001-M"]["preco_unitario"]) == Decimal("90.00")
        assert por_sku["P001-M"]["preco_manual"] is False
        assert Decimal(por_sku["P001-G"]["desconto"]) == Decimal("8.00")
        assert por_sku["P001-G"]["descricao"]
        assert Decimal(data["total_pedido"]) == Decimal("252.00")

        id_m, id_g = por_sku["P001-M"]["id"], por_sku["P001-G"]["id"]
        res = client.put(
            _url(pedido, "/itens"),
            headers=headers_admin,
            json={
                "criar": [{"ref_temp": 3, "sku_codigo": "P001-M", "quantidade": 1, "preco_unitario": "50"}],
                "atualizar": [{"item_id": id_m, "quantidade": 3, "desconto": "20"}],
                "remover": [id_g],
            },
        )
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert len(data["itens"]) == 2
        # 3 × 90 − 20 + 1 × 50 (preço manual)
        assert Decimal(data["total_pedido"]) == Decimal("300.00")

    def test_um_item_invalido_nao_salva_nenhum(self, client, headers_admin, db_session, cliente, skus):
        m, _ = skus
        pedido = _criar_pedido(client, headers_admin, cliente)
        criado = client.put(
            _url(pedido, "/itens"),
            headers=headers_admin,
            json={"criar": [{"ref_temp": "a", "sku_id": m.id, "quantidade": 1}]},
        ).json()["data"]["itens"][0]

        res = client.put(
            _url(pedido, "/itens"),
            headers=headers_admin,
            json={
                "criar": [
                    {"ref_temp": "ok", "sku_id": m.id, "quantidade": 5},
                    {"ref_temp": "ruim", "sku_codigo": "NAO-EXISTE", "quantidade": 1},
                ],
                "atualizar": [
                    {"item_id": criado["id"], "quantidade": 4},
                    {"item_id": criado["id"], "tes_codigo": "XYZ"},
                ],
            },
        )
        assert res.status_code == 422
        erros = res.json()["erros"]
        assert any(e.get("ref_temp") == "ruim" and e["campo"] == "sku_codigo" for e in erros)
        assert any(e.get("item_id") == criado["id"] and e["campo"] == "tes_codigo" for e in erros)
        assert len(erros) == 2

        itens = _itens_no_banco(db_session, pedido)
        assert len(itens) == 1
        assert itens[0].quantidade == 1

    def test_erros_de_campo(self, client, headers_admin, cliente, skus):
        m, _ = skus
        pedido = _criar_pedido(client, headers_admin, cliente)
        res = client.put(
            _url(pedido, "/itens"),
            headers=headers_admin,
            json={
                "criar": [
                    {"ref_temp": 1, "sku_id": m.id},
                    {"ref_temp": 2, "sku_id": 9999, "quantidade": 1},
                    {"ref_temp": 3, "sku_id": m.id, "quantidade": 1, "desconto": "500"},
                    {"ref_temp": 4, "sku_id": m.id, "quantidade": 1, "desconto_percentual": "101"},
                ],
                "remover": ["00000000-0000-0000-0000-000000000000"],
            },
        )
        assert res.status_code == 422
        campos = {(e.get("ref_temp") or e.get("item_id"), e["campo"]) for e in res.json()["erros"]}
        assert campos == {
            (1, "quantidade"),
            (2, "sku_id"),
            (3, "desconto"),
            (4, "desconto_percentual"),
            ("00000000-0000-0000-0000-000000000000", "item_id"),
        }

    def test_pedido_fechado_409(self, client, headers_admin, db_session, cliente, skus):
        m, _ = skus
        pedido = _criar_pedido(client, headers_admin, cliente)
        client.patch(_url(pedido, "/status"), headers=headers_admin, json={"status": "Fechado"})
        res = client.put(
            _url(pedido, "/itens"),
            headers=headers_admin,
            json={"criar": [{"ref_temp": 1, "sku_id": m.id, "quantidade": 1}]},
        )
        assert res.status_code == 409


class TestSalvarPedidoComItens:
    def test_grava_cabecalho_e_itens_juntos(self, client, headers_admin, cliente, skus):
        m, _ = skus
        pedido = _criar_pedido(client, headers_admin, cliente)
        res = client.put(
            _url(pedido),
            headers=headers_admin,
            json={
                "valor_frete": "10",
                "itens": {"criar": [{"ref_temp": "x", "sku_id": m.id, "quantidade": 2}]},
            },
        )
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert len(data["itens"]) == 1
        assert Decimal(data["total_pedido"]) == Decimal("190.00")

    def test_item_invalido_nao_salva_cabecalho(self, client, headers_admin, db_session, cliente, skus):
        pedido = _criar_pedido(client, headers_admin, cliente)
        res = client.put(
            _url(pedido),
            headers=headers_admin,
            json={
                "valor_frete": "10",
                "informacoes_adicionais": "NAO DEVE GRAVAR",
                "itens": {"criar": [{"ref_temp": "x", "sku_codigo": "NAO-EXISTE", "quantidade": 2}]},
            },
        )
        assert res.status_code == 422
        assert res.json()["erros"] == [
            {"ref_temp": "x", "campo": "sku_codigo", "mensagem": "Código de produto inválido: NAO-EXISTE"}
        ]
        db_session.expire_all()
        p = db_session.get(PedidoVenda, uuid.UUID(pedido["id"]))
        assert not p.valor_frete
        assert p.informacoes_adicionais != "NAO DEVE GRAVAR"
        assert _itens_no_banco(db_session, pedido) == []

    def test_patch_item_individual_continua(self, client, headers_admin, cliente, skus):
        m, _ = skus
        pedido = _criar_pedido(client, headers_admin, cliente)
        item = client.put(
            _url(pedido, "/itens"),
            headers=headers_admin,
            json={"criar": [{"ref_temp": 1, "sku_id": m.id, "quantidade": 1}]},
        ).json()["data"]["itens"][0]
        res = client.patch(_url(pedido, f"/itens/{item['id']}"), headers=headers_admin, json={"quantidade": 0})
        assert res.status_code == 422
        assert res.json()["detail"] == "Quantidade deve ser maior que zero."
        res = client.patch(_url(pedido, f"/itens/{item['id']}"), headers=headers_admin, json={"quantidade": 2})
        assert res.status_code == 200, res.text
        assert Decimal(res.json()["data"]["totais"]["total"]) == Decimal("180.00")
