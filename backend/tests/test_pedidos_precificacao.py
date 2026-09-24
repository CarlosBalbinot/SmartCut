"""Testes de pedidos de venda e precificação (Parte 8.1 — itens 2 e 3).

Cobre: criação de pedido com snapshot do cliente, item legado (grupo de
moldes) precificado pela tabela, item do catálogo fiscal (produto/SKU) onde a
tabela prevalece sobre o preco manual, recálculo de totais (subtotal,
desconto, frete, comissão) e o fluxo aplicar-tabela (reprecifica e limpa o
preço manual, devolvendo em "sem_preco" o que não tem preço na tabela).
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from models.cliente import Cliente
from models.grupo_molde import GrupoMolde
from models.pedido import ItemPedido, PedidoVenda
from models.produto import GrupoProduto, Produto
from models.produto_sku import ProdutoSKU
from models.venda import PrecoReferencia, PrecoTabelaProduto, TabelaPreco
from services import venda_service


@pytest.fixture()
def cliente(db_session):
    c = Cliente(
        codigo="0001",
        tipo_registro="cliente",
        tipo_pessoa="juridica",
        razao_social="CLIENTE LTDA",
        cnpj="12345678000190",
        endereco="RUA A",
        numero="10",
        bairro="CENTRO",
        cidade="CAXIAS DO SUL",
        estado="RS",
        cep="95000000",
        codigo_ibge_municipio="4305108",
    )
    db_session.add(c)
    db_session.commit()
    return c


def _criar_pedido(client, headers_admin, cliente, **extra):
    payload = {
        "tipo": "venda",
        "cliente_id": cliente.id,
        "data_emissao": "2026-09-10",
        "condicoes": "avista",
        "prazo_entrega_dias": 20,
    }
    payload.update(extra)
    res = client.post("/api/v1/pedidos-venda/", headers=headers_admin, json=payload)
    assert res.status_code == 200, res.text
    return res.json()["data"]


def _nova_tabela(db_session, nome="TABELA TESTE") -> TabelaPreco:
    tabela = TabelaPreco(nome=nome, comissao_pct=None, ativa=True)
    db_session.add(tabela)
    db_session.commit()
    return tabela


class TestCriacaoPedido:
    def test_criar_com_snapshot_do_cliente(self, client, headers_admin, cliente):
        data = _criar_pedido(client, headers_admin, cliente)
        assert data["status"] == "Aberto"
        assert data["cliente_razao_social"] == "CLIENTE LTDA"
        assert data["cliente_cnpj"] == "12345678000190"
        assert Decimal(data["total_pedido"]) == Decimal("0")

    def test_pedido_venda_exige_cliente(self, client, headers_admin):
        res = client.post(
            "/api/v1/pedidos-venda/",
            headers=headers_admin,
            json={
                "tipo": "venda",
                "data_emissao": "2026-09-10",
            },
        )
        assert res.status_code == 422
        assert "cliente" in res.json()["detail"]

    def test_sem_autenticacao_401(self, client):
        res = client.post(
            "/api/v1/pedidos-venda/",
            json={
                "tipo": "venda",
                "data_emissao": "2026-09-10",
            },
        )
        assert res.status_code == 401


class TestPrecificacaoLegado:
    def test_preco_vem_da_tabela_do_grupo(self, client, headers_admin, db_session, cliente):
        tabela = _nova_tabela(db_session)
        grupo = GrupoMolde(nome="CALCA")
        db_session.add(grupo)
        db_session.commit()
        db_session.add(
            PrecoReferencia(
                grupo_id=grupo.id,
                tabela_id=tabela.id,
                preco_avista=Decimal("50.00"),
                preco_aprazo=Decimal("55.00"),
            )
        )
        db_session.commit()

        pedido = _criar_pedido(client, headers_admin, cliente, tabela_preco_id=str(tabela.id))
        res = client.post(
            f"/api/v1/pedidos-venda/{pedido['id']}/itens",
            headers=headers_admin,
            json={"grupo_id": str(grupo.id), "qtd_p": 1, "qtd_m": 2},
        )
        assert res.status_code == 200, res.text
        item = res.json()["data"]
        # 3 peças × 50,00 (à vista) → bruto 150,00; preço veio da tabela.
        assert Decimal(item["preco_unitario"]) == Decimal("50.00")
        assert Decimal(item["preco_total"]) == Decimal("150.00")
        assert item["preco_manual"] is False

        final = client.get(f"/api/v1/pedidos-venda/{pedido['id']}", headers=headers_admin).json()["data"]
        assert Decimal(final["total_pedido"]) == Decimal("150.00")


class TestPrecificacaoCatalogo:
    @pytest.fixture()
    def grupo_produto(self, db_session):
        g = GrupoProduto(codigo="G01", nome="GRUPO TESTE", prefixo="GT")
        db_session.add(g)
        db_session.commit()
        return g

    @pytest.fixture()
    def produto(self, db_session, grupo_produto):
        p = Produto(
            grupo_id=grupo_produto.id,
            codigo="P001",
            descricao="PRODUTO TESTE",
            unidade="UN",
            preco_venda=Decimal("80.00"),
            ncm="61091000",
            origem=0,
        )
        db_session.add(p)
        db_session.commit()
        return p

    @pytest.fixture()
    def sku(self, db_session, produto):
        s = ProdutoSKU(
            produto_pai_id=produto.id,
            codigo="P001-M",
            preco_venda=Decimal("90.00"),
            preco_manual=True,
        )
        db_session.add(s)
        db_session.commit()
        return s

    def test_tabela_prevalece_sobre_preco_digitado(self, client, headers_admin, db_session, cliente, produto, sku):
        tabela = _nova_tabela(db_session, "TABELA CATALOGO")
        db_session.add(
            PrecoTabelaProduto(
                tabela_preco_id=tabela.id,
                sku_id=sku.id,
                preco_avista=Decimal("60.00"),
                preco_aprazo=Decimal("65.00"),
            )
        )
        db_session.commit()

        pedido = _criar_pedido(client, headers_admin, cliente, tabela_preco_id=str(tabela.id))
        res = client.post(
            f"/api/v1/pedidos-venda/{pedido['id']}/itens/bulk",
            headers=headers_admin,
            json={
                "itens": [
                    {
                        "produto_id": str(produto.id),
                        "sku_id": sku.id,
                        "quantidade": 3,
                        "preco_unitario": "99.99",
                    }
                ]
            },
        )
        assert res.status_code == 200, res.text
        item = res.json()["data"][0]
        # Preço da tabela (SKU → 60,00) vence os 99,99 do payload.
        assert Decimal(item["preco_unitario"]) == Decimal("60.00")
        assert Decimal(item["preco_total"]) == Decimal("180.00")

        final = client.get(f"/api/v1/pedidos-venda/{pedido['id']}", headers=headers_admin).json()["data"]
        assert Decimal(final["total_pedido"]) == Decimal("180.00")


class TestAplicarTabela:
    def test_reprecifica_e_limpa_preco_manual(self, client, headers_admin, db_session, cliente):
        tabela = _nova_tabela(db_session, "TABELA FIM")
        grupo = GrupoMolde(nome="BLUSA")
        db_session.add(grupo)
        db_session.commit()
        db_session.add(
            PrecoReferencia(
                grupo_id=grupo.id,
                tabela_id=tabela.id,
                preco_avista=Decimal("45.00"),
                preco_aprazo=Decimal("50.00"),
            )
        )
        db_session.commit()

        # Pedido SEM tabela e preço digitado à mão no item.
        pedido = _criar_pedido(client, headers_admin, cliente, condicoes="aprazo")
        res = client.post(
            f"/api/v1/pedidos-venda/{pedido['id']}/itens",
            headers=headers_admin,
            json={"grupo_id": str(grupo.id), "qtd_p": 1, "preco_unitario": "120.00"},
        )
        assert res.status_code == 200, res.text
        item = res.json()["data"]
        assert Decimal(item["preco_unitario"]) == Decimal("120.00")
        assert item["preco_manual"] is True

        res = client.post(
            f"/api/v1/pedidos-venda/{pedido['id']}/aplicar-tabela",
            headers=headers_admin,
            json={"tabela_preco_id": str(tabela.id)},
        )
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["sem_preco"] == []
        item = data["pedido"]["itens"][0]
        # condicoes="aprazo" → preço a prazo da tabela; manual limpo.
        assert Decimal(item["preco_unitario"]) == Decimal("50.00")
        assert item["preco_manual"] is False
        assert Decimal(data["pedido"]["total_pedido"]) == Decimal("50.00")

    def test_item_sem_preco_na_tabela_vai_para_sem_preco(self, client, headers_admin, db_session, cliente):
        tabela = _nova_tabela(db_session, "TABELA VAZIA")
        grupo = GrupoMolde(nome="SEM PRECO")  # sem PrecoReferencia
        db_session.add(grupo)
        db_session.commit()

        pedido = _criar_pedido(client, headers_admin, cliente)
        res = client.post(
            f"/api/v1/pedidos-venda/{pedido['id']}/itens",
            headers=headers_admin,
            json={"grupo_id": str(grupo.id), "qtd_p": 1, "preco_unitario": "99.00"},
        )
        assert res.status_code == 200, res.text

        res = client.post(
            f"/api/v1/pedidos-venda/{pedido['id']}/aplicar-tabela",
            headers=headers_admin,
            json={"tabela_preco_id": str(tabela.id)},
        )
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["sem_preco"]  # grupo sem preço fica na lista
        item = data["pedido"]["itens"][0]
        # Sem preço na tabela o manual é mantido.
        assert Decimal(item["preco_unitario"]) == Decimal("99.00")


class TestCalculoTotais:
    def _item(self, pedido_id, quantidade=1, preco=Decimal("100.00"), desconto_valor=0, acrescimo_valor=0):
        return ItemPedido(
            pedido_id=pedido_id,
            produto_id=uuid.uuid4(),  # FK não é imposta no SQLite de teste
            quantidade=quantidade,
            preco_unitario=preco,
            preco_total=preco * quantidade,
            desconto_valor=desconto_valor,
            acrescimo_valor=acrescimo_valor,
            desconto_tipo="VALOR",
        )

    def test_subtotal_liquido_e_comissao(self):
        pid = uuid.uuid4()
        itens = [
            self._item(pid, quantidade=2, preco=Decimal("100.00"), desconto_valor=20),
            self._item(pid, quantidade=1, preco=Decimal("50.00"), acrescimo_valor=5),
        ]
        subtotal = venda_service.calcular_subtotal_itens(itens)
        assert subtotal == Decimal("235.00")  # (200-20) + (50+5)

        subtotal2, comissao = venda_service.calcular_totais(itens, "10")
        assert subtotal2 == Decimal("235.00")
        assert comissao == Decimal("23.50")

    def test_recalcular_pedido_com_desconto_geral_e_frete(self, db_session):
        pedido = PedidoVenda(
            numero="000001",
            tipo="venda",
            data_emissao=date(2026, 9, 10),
            status="Aberto",
            desconto_geral_valor=Decimal("10.00"),
            valor_frete=Decimal("5.00"),
        )
        db_session.add(pedido)
        db_session.flush()
        db_session.add(self._item(pedido.id, quantidade=1, preco=Decimal("150.00")))
        db_session.commit()

        venda_service.recalcular_pedido(db_session, pedido.id)
        # recalcular_pedido não commita — o chamador real (router) commita.
        db_session.commit()
        db_session.refresh(pedido)
        assert Decimal(pedido.total_pedido) == Decimal("145.00")
        assert Decimal(pedido.comissao_valor) == Decimal("0")
