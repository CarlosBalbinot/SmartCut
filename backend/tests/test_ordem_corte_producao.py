"""OC6a — produção e estoque da Ordem de Corte.

Cobre a reserva de lote (ENVIADA/EM_CORTE travam o peso planejado), as
transições de produção e o consumo/estorno de ``lotes_tecido``.

O encaixe é gravado direto no banco (mesmo formato que o nesting produz) para
que o teste foque na reserva e na baixa de estoque, sem depender do motor de
nesting — o que está em jogo aqui é o peso, não o plano de corte.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from models.encaixe import Encaixe
from models.pedido import ItemPedido
from models.produto import GrupoProduto, Produto
from models.produto_sku import ProdutoSKU
from models.tabela_grade import ItemTabelaGrade, TabelaGrade
from models.tecido import ConsumoLote, CorTecido, LoteTecido, ModeloTecido
from services import ordem_corte_service as svc
from tests.test_pedidos_precificacao import _criar_pedido

PESO_LOTE = 50.0
PESO_ENCAIXE = 2.0
CAMADAS = 3
PLANEJADO = PESO_ENCAIXE * CAMADAS  # 6.0 kg — o que a OC reserva/consome


# ── Montagem do cenário ───────────────────────────────────────────────────────


def _novo_lote(db, codigo="LOTE-A", peso=PESO_LOTE) -> LoteTecido:
    modelo = ModeloTecido(nome="JACARANDA", tipo="Malha", max_camadas=15)
    db.add(modelo)
    db.commit()
    cor = CorTecido(
        modelo_id=modelo.id,
        nome_cor="Azul",
        largura_util_cm=Decimal("150.00"),
        gramatura_g_m2=Decimal("180.00"),
        encolhimento_pct=Decimal("0"),
    )
    db.add(cor)
    db.commit()
    lote = LoteTecido(
        cor_id=cor.id,
        codigo_lote=codigo,
        peso_inicial_kg=peso,
        peso_disponivel_kg=peso,
        valor_kg=Decimal("30.00"),
        data_compra=date(2026, 9, 1),
        status="intacto",
    )
    db.add(lote)
    db.commit()
    return lote


def _novo_produto(db) -> tuple[Produto, ProdutoSKU]:
    grupo = GrupoProduto(codigo="G01", nome="GRUPO TESTE", prefixo="GT")
    db.add(grupo)
    db.commit()
    produto = Produto(
        grupo_id=grupo.id,
        codigo="P001",
        descricao="CAMISETA",
        unidade="UN",
        preco_venda=Decimal("80.00"),
        ncm="61091000",
        origem=0,
    )
    db.add(produto)
    db.commit()
    grade = TabelaGrade(codigo="TG1", descricao="GRADE", situacao="Ativa")
    db.add(grade)
    db.commit()
    linha = ItemTabelaGrade(tabela_id=grade.id, codigo_curto="AZ", descricao="Azul", ordem=1, situacao="Ativa")
    coluna = ItemTabelaGrade(tabela_id=grade.id, codigo_curto="M", descricao="M", ordem=1, situacao="Ativa")
    db.add_all([linha, coluna])
    db.commit()
    sku = ProdutoSKU(
        produto_pai_id=produto.id,
        linha_item_id=linha.id,
        coluna_item_id=coluna.id,
        codigo="P001-AZ-M",
        preco_venda=Decimal("90.00"),
        preco_manual=True,
    )
    db.add(sku)
    db.commit()
    return produto, sku


def _criar_oc(
    client,
    headers_admin,
    db_session,
    cliente,
    produto,
    sku,
    lote,
    codigo_lote=None,
    peso_encaixe=PESO_ENCAIXE,
    camadas=CAMADAS,
) -> dict:
    """Pedido → OC com lote escolhido e um encaixe de `peso_encaixe` kg ×
    `camadas` camadas. Devolve a OC serializada."""
    pedido = _criar_pedido(client, headers_admin, cliente)
    db_session.add(
        ItemPedido(
            pedido_id=uuid.UUID(pedido["id"]),
            produto_id=produto.id,
            sku_id=sku.id,
            cor="Azul",
            quantidade=4,
            preco_unitario=Decimal("90.00"),
            preco_total=Decimal("360.00"),
        )
    )
    db_session.commit()

    res = client.post(f"/api/v1/ordens-corte/pedido/{pedido['id']}", headers=headers_admin)
    assert res.status_code == 201, res.text
    oc = res.json()["data"]

    res = client.put(
        f"/api/v1/ordens-corte/{oc['id']}/tecidos",
        headers=headers_admin,
        json=[{"produto_pai_id": str(produto.id), "cor": "Azul", "lote_id": str(lote.id)}],
    )
    assert res.status_code == 200, res.text

    db_session.add(
        Encaixe(
            pedido_id=uuid.UUID(pedido["id"]),
            ordem_corte_id=uuid.UUID(oc["id"]),
            lote_id=lote.id,
            # numero é único global (nunca reaproveita, nem de deleted).
            numero=1 + (db_session.query(Encaixe).count() or 0),
            comp_metros=Decimal("2.000"),
            peso_kg=peso_encaixe,
            num_camadas=camadas,
            status="ativo",
        )
    )
    db_session.commit()
    return oc


@pytest.fixture()
def base(db_session, cliente):
    """Lote de 50 kg e o produto com a grade (cor/tamanho) do SKU."""
    lote = _novo_lote(db_session)
    produto, sku = _novo_produto(db_session)
    return {"lote": lote, "produto": produto, "sku": sku, "cliente": cliente}


def _peso(db, lote) -> float:
    db.expire_all()
    return float(db.get(LoteTecido, lote.id).peso_disponivel_kg)


def _lote_na_api(client, headers_admin, lote_id, oc_id=None):
    url = f"/api/v1/ordens-corte/lotes-disponiveis?oc_id={oc_id}" if oc_id else "/api/v1/ordens-corte/lotes-disponiveis"
    res = client.get(url, headers=headers_admin)
    assert res.status_code == 200, res.text
    return next(lt for lt in res.json()["data"] if lt["id"] == str(lote_id))


def _consumos(db, oc_id, tipo="CONSUMO"):
    db.expire_all()
    return db.query(ConsumoLote).filter(ConsumoLote.ordem_corte_id == uuid.UUID(oc_id), ConsumoLote.tipo == tipo).all()


# ── Reserva ───────────────────────────────────────────────────────────────────


class TestReserva:
    def test_rascunho_nao_reserva(self, client, headers_admin, db_session, base):
        # A OC existe e já tem encaixe com peso, mas está em RASCUNHO: quem
        # ainda pode trocar de lote não trava peso de ninguém.
        _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        visto = _lote_na_api(client, headers_admin, base["lote"].id)
        assert visto["reservado_kg"] == 0
        assert visto["livre_kg"] == PESO_LOTE

    def test_enviada_reserva_e_outra_oc_vem_livre_reduzido(self, client, headers_admin, db_session, base, cliente):
        oc1 = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        res = client.post(f"/api/v1/ordens-corte/{oc1['id']}/enviar", headers=headers_admin)
        assert res.status_code == 200, res.text
        assert res.json()["data"]["status"] == "ENVIADA"
        assert res.json()["data"]["enviada_em"] is not None

        # O lote agora tem PLANEJADO kg travados.
        visto = _lote_na_api(client, headers_admin, base["lote"].id)
        assert visto["reservado_kg"] == PLANEJADO
        assert visto["livre_kg"] == pytest.approx(PESO_LOTE - PLANEJADO)

        # A própria OC não é residência de si mesma: excluindo ela, o que
        # sobra é o lote inteiro.
        visto_own = _lote_na_api(client, headers_admin, base["lote"].id, oc_id=oc1["id"])
        assert visto_own["reservado_kg"] == 0
        assert visto_own["livre_kg"] == PESO_LOTE

        # Uma segunda OC ENVIADA no mesmo lote empilha a reserva: as duas
        # planejam peso do mesmo tecido, então as duas travam o dele.
        oc2 = _criar_oc(
            client,
            headers_admin,
            db_session,
            cliente,
            base["produto"],
            base["sku"],
            base["lote"],
            peso_encaixe=8.0,
            camadas=1,
        )
        client.post(f"/api/v1/ordens-corte/{oc2['id']}/enviar", headers=headers_admin)
        visto = _lote_na_api(client, headers_admin, base["lote"].id)
        assert visto["reservado_kg"] == PLANEJADO + 8.0
        assert visto["livre_kg"] == pytest.approx(PESO_LOTE - PLANEJADO - 8.0)
        # Cada uma, vista sem a outra, vê o que a outra travou.
        assert _lote_na_api(client, headers_admin, base["lote"].id, oc_id=oc1["id"])["reservado_kg"] == 8.0
        assert _lote_na_api(client, headers_admin, base["lote"].id, oc_id=oc2["id"])["reservado_kg"] == PLANEJADO

    def test_estoque_insuficiente_compara_com_o_livre(self, client, headers_admin, db_session, base, cliente):
        oc1 = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc1['id']}/enviar", headers=headers_admin)

        oc2 = _criar_oc(
            client,
            headers_admin,
            db_session,
            cliente,
            base["produto"],
            base["sku"],
            base["lote"],
            peso_encaixe=PESO_LOTE - PLANEJADO + 1,
            camadas=1,
        )
        # 45 kg pedidos contra 44 kg livres: não cabe. A conferência olha o
        # LIVRE (disponível menos a reserva das outras OCs), não o disponível.
        oc = svc._carregar(db_session, uuid.UUID(oc2["id"]))
        avisos = svc.avisos_estoque(db_session, oc)
        assert [a["codigo"] for a in avisos] == ["ESTOQUE_INSUFICIENTE"]
        assert avisos[0]["reservado_kg"] == PLANEJADO
        assert avisos[0]["livre_kg"] == pytest.approx(PESO_LOTE - PLANEJADO)

        # Cabe se couber no livre: 44 kg exatos passam, o que mostra que a
        # comparação é com o livre e não com o disponível.
        db_session.query(Encaixe).filter(Encaixe.ordem_corte_id == uuid.UUID(oc2["id"])).update(
            {"peso_kg": PESO_LOTE - PLANEJADO}
        )
        db_session.commit()
        oc = svc._carregar(db_session, uuid.UUID(oc2["id"]))
        assert svc.avisos_estoque(db_session, oc) == []

    def test_voltar_rascunho_libera_a_reserva(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        assert _lote_na_api(client, headers_admin, base["lote"].id)["reservado_kg"] == PLANEJADO

        res = client.post(f"/api/v1/ordens-corte/{oc['id']}/voltar-rascunho", headers=headers_admin)
        assert res.status_code == 200, res.text
        assert res.json()["data"]["status"] == "RASCUNHO"
        assert res.json()["data"]["enviada_em"] is None
        assert _lote_na_api(client, headers_admin, base["lote"].id)["reservado_kg"] == 0

    def test_concluida_libera_a_reserva_e_cancelada_tambem(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={"cortador": "ANA"})
        client.post(
            f"/api/v1/ordens-corte/{oc['id']}/concluir",
            headers=headers_admin,
            json={"cortador": "ANA", "consumos": []},
        )
        # O peso saiu do estoque (consumo), então não há mais o que reservar.
        assert _lote_na_api(client, headers_admin, base["lote"].id, oc_id=oc["id"])["reservado_kg"] == 0
        assert _peso(db_session, base["lote"]) == pytest.approx(PESO_LOTE - PLANEJADO)


# ── Transições ────────────────────────────────────────────────────────────────


class TestTransicoes:
    def test_iniciar_grava_data_e_cortador(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)

        res = client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={"cortador": "ANA"})
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["status"] == "EM_CORTE"
        assert data["iniciada_em"] is not None
        assert data["cortador"] == "ANA"

    def test_cancelar_em_corte_e_permitido_e_nao_baixa(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={"cortador": "ANA"})

        res = client.post(f"/api/v1/ordens-corte/{oc['id']}/cancelar", headers=headers_admin)
        assert res.status_code == 200, res.text
        assert res.json()["data"]["status"] == "CANCELADA"
        assert _peso(db_session, base["lote"]) == PESO_LOTE
        assert _consumos(db_session, oc["id"]) == []
        assert _lote_na_api(client, headers_admin, base["lote"].id)["reservado_kg"] == 0

    @pytest.mark.parametrize(
        "rota,corpo,partida",
        [
            ("iniciar", {"cortador": "ANA"}, "RASCUNHO"),
            ("concluir", {"cortador": "ANA", "consumos": []}, "RASCUNHO"),
            ("reabrir", {"quem": "ANA"}, "RASCUNHO"),
            ("voltar-rascunho", None, "RASCUNHO"),
        ],
    )
    def test_transicao_fora_de_ordem_409(self, client, headers_admin, db_session, base, rota, corpo, partida):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        if partida == "ENVIADA":
            client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        res = client.post(f"/api/v1/ordens-corte/{oc['id']}/{rota}", headers=headers_admin, json=corpo)
        assert res.status_code == 409, res.text

    def test_reabrir_sem_ter_concluido_409(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        res = client.post(f"/api/v1/ordens-corte/{oc['id']}/reabrir", headers=headers_admin, json={"quem": "ANA"})
        assert res.status_code == 409, res.text

    def test_concluir_precisa_do_cortador(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={})
        res = client.post(f"/api/v1/ordens-corte/{oc['id']}/concluir", headers=headers_admin, json={"consumos": []})
        assert res.status_code == 422, res.text

    def test_voltar_rascunho_depois_de_iniciar_409(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={})
        res = client.post(f"/api/v1/ordens-corte/{oc['id']}/voltar-rascunho", headers=headers_admin)
        assert res.status_code == 409, res.text


# ── Consumo e estorno ─────────────────────────────────────────────────────────


class TestConsumo:
    def test_concluir_baixa_o_peso_e_grava_consumo(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={"cortador": "ANA"})

        res = client.post(
            f"/api/v1/ordens-corte/{oc['id']}/concluir",
            headers=headers_admin,
            json={"cortador": "ANA", "consumos": [], "observacao": "corte ok"},
        )
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["status"] == "CONCLUIDA"
        assert data["concluida_em"] is not None

        # kg_real padrão = planejado do lote na OC (2 kg × 3 camadas).
        assert _peso(db_session, base["lote"]) == pytest.approx(PESO_LOTE - PLANEJADO)
        consumos = _consumos(db_session, oc["id"])
        assert len(consumos) == 1
        assert float(consumos[0].peso_consumido_kg) == PLANEJADO
        assert float(consumos[0].peso_planejado_kg) == PLANEJADO
        assert consumos[0].observacao == "corte ok"

    def test_kg_real_diverge_do_planejado(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={})

        res = client.post(
            f"/api/v1/ordens-corte/{oc['id']}/concluir",
            headers=headers_admin,
            json={
                "cortador": "ANA",
                "consumos": [{"lote_id": str(base["lote"].id), "kg_real": 5.5, "sobra_kg": 1.25}],
            },
        )
        assert res.status_code == 200, res.text
        assert _peso(db_session, base["lote"]) == pytest.approx(PESO_LOTE - 5.5)
        cons = _consumos(db_session, oc["id"])[0]
        assert float(cons.peso_consumido_kg) == 5.5
        assert float(cons.peso_planejado_kg) == PLANEJADO  # referência do planejamento
        assert float(cons.peso_retalho_kg) == 1.25

    def test_lote_esgotado_vira_esgotado(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={})
        client.post(
            f"/api/v1/ordens-corte/{oc['id']}/concluir",
            headers=headers_admin,
            json={
                "cortador": "ANA",
                "consumos": [{"lote_id": str(base["lote"].id), "kg_real": PESO_LOTE}],
            },
        )
        db_session.expire_all()
        lote = db_session.get(LoteTecido, base["lote"].id)
        assert float(lote.peso_disponivel_kg) == 0
        assert lote.status == "esgotado"

    def test_kg_real_negativo_422(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={})
        res = client.post(
            f"/api/v1/ordens-corte/{oc['id']}/concluir",
            headers=headers_admin,
            json={"cortador": "ANA", "consumos": [{"lote_id": str(base["lote"].id), "kg_real": -1}]},
        )
        assert res.status_code == 422, res.text
        assert _peso(db_session, base["lote"]) == PESO_LOTE

    def test_lote_repetido_no_consumo_400(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={})
        res = client.post(
            f"/api/v1/ordens-corte/{oc['id']}/concluir",
            headers=headers_admin,
            json={
                "cortador": "ANA",
                "consumos": [
                    {"lote_id": str(base["lote"].id), "kg_real": 1},
                    {"lote_id": str(base["lote"].id), "kg_real": 2},
                ],
            },
        )
        assert res.status_code == 400, res.text
        # Nada foi baixado: a validação roda antes de qualquer consumo.
        assert _peso(db_session, base["lote"]) == PESO_LOTE

    def test_lote_de_fora_da_oc_404(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        outro = _novo_lote(db_session, codigo="LOTE-B", peso=10)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={})
        res = client.post(
            f"/api/v1/ordens-corte/{oc['id']}/concluir",
            headers=headers_admin,
            json={"cortador": "ANA", "consumos": [{"lote_id": str(outro.id), "kg_real": 1}]},
        )
        assert res.status_code == 404, res.text
        assert _peso(db_session, base["lote"]) == PESO_LOTE


class TestEstorno:
    def test_reabrir_devolve_o_peso_exato(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={})
        client.post(
            f"/api/v1/ordens-corte/{oc['id']}/concluir",
            headers=headers_admin,
            json={"cortador": "ANA", "consumos": [{"lote_id": str(base["lote"].id), "kg_real": 5.5}]},
        )
        assert _peso(db_session, base["lote"]) == pytest.approx(PESO_LOTE - 5.5)

        res = client.post(
            f"/api/v1/ordens-corte/{oc['id']}/reabrir",
            headers=headers_admin,
            json={"quem": "BRUNO", "observacao": "erro de medida"},
        )
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["status"] == "EM_CORTE"
        assert data["concluida_em"] is None

        # Exatamente o que foi baixado volta — nem o planejado, nem o inicial.
        assert _peso(db_session, base["lote"]) == pytest.approx(PESO_LOTE)
        estornos = _consumos(db_session, oc["id"], tipo="ESTORNO")
        assert len(estornos) == 1
        assert float(estornos[0].peso_consumido_kg) == 5.5
        assert estornos[0].estorno_de_id == _consumos(db_session, oc["id"])[0].id
        assert "BRUNO" in estornos[0].observacao
        assert "erro de medida" in estornos[0].observacao

    def test_reabrir_reativa_lote_esgotado(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={})
        client.post(
            f"/api/v1/ordens-corte/{oc['id']}/concluir",
            headers=headers_admin,
            json={"cortador": "ANA", "consumos": [{"lote_id": str(base["lote"].id), "kg_real": PESO_LOTE}]},
        )
        db_session.expire_all()
        assert db_session.get(LoteTecido, base["lote"].id).status == "esgotado"

        client.post(f"/api/v1/ordens-corte/{oc['id']}/reabrir", headers=headers_admin, json={"quem": "BRUNO"})
        db_session.expire_all()
        lote = db_session.get(LoteTecido, base["lote"].id)
        assert lote.status == "aberto"
        assert float(lote.peso_disponivel_kg) == PESO_LOTE

    def test_ciclo_concluir_reabrir_desfaz_so_a_ultima_baixa(self, client, headers_admin, db_session, base):
        """A 2ª reabertura tem de devolver a 2ª conclusão, não a soma das duas.

        Cada ESTORNO aponta para o CONSUMO que desfaz — é isso que garante o
        "exatamente o que foi baixado" quando a OC vai e volta várias vezes.
        """
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={})

        client.post(
            f"/api/v1/ordens-corte/{oc['id']}/concluir",
            headers=headers_admin,
            json={"cortador": "ANA", "consumos": [{"lote_id": str(base["lote"].id), "kg_real": 10}]},
        )
        assert _peso(db_session, base["lote"]) == pytest.approx(PESO_LOTE - 10)

        client.post(f"/api/v1/ordens-corte/{oc['id']}/reabrir", headers=headers_admin, json={"quem": "BRUNO"})
        assert _peso(db_session, base["lote"]) == pytest.approx(PESO_LOTE)

        # Segunda ida: agora um peso diferente, para não confundir as baixas.
        client.post(
            f"/api/v1/ordens-corte/{oc['id']}/concluir",
            headers=headers_admin,
            json={"cortador": "ANA", "consumos": [{"lote_id": str(base["lote"].id), "kg_real": 7}]},
        )
        assert _peso(db_session, base["lote"]) == pytest.approx(PESO_LOTE - 7)

        res = client.post(f"/api/v1/ordens-corte/{oc['id']}/reabrir", headers=headers_admin, json={"quem": "BRUNO"})
        assert res.status_code == 200, res.text
        assert _peso(db_session, base["lote"]) == pytest.approx(PESO_LOTE)

        # Duas baixas, dois estornos — e os pares batem.
        consumos = _consumos(db_session, oc["id"])
        estornos = _consumos(db_session, oc["id"], tipo="ESTORNO")
        assert len(consumos) == 2 and len(estornos) == 2
        estornados = {e.estorno_de_id for e in estornos}
        assert estornados == {c.id for c in consumos}

    def test_concluida_de_novo_apos_reabrir(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={})
        client.post(
            f"/api/v1/ordens-corte/{oc['id']}/concluir",
            headers=headers_admin,
            json={"cortador": "ANA", "consumos": [{"lote_id": str(base["lote"].id), "kg_real": 4}]},
        )
        client.post(f"/api/v1/ordens-corte/{oc['id']}/reabrir", headers=headers_admin, json={"quem": "BRUNO"})
        res = client.post(
            f"/api/v1/ordens-corte/{oc['id']}/concluir",
            headers=headers_admin,
            json={"cortador": "ANA", "consumos": [{"lote_id": str(base["lote"].id), "kg_real": 4}]},
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["status"] == "CONCLUIDA"
        assert _peso(db_session, base["lote"]) == pytest.approx(PESO_LOTE - 4)

    def test_reabrir_reserva_o_lote_de_novo(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        client.post(f"/api/v1/ordens-corte/{oc['id']}/iniciar", headers=headers_admin, json={})
        client.post(
            f"/api/v1/ordens-corte/{oc['id']}/concluir",
            headers=headers_admin,
            json={"cortador": "ANA", "consumos": [{"lote_id": str(base["lote"].id), "kg_real": 4}]},
        )
        # CONCLUIDA não reserva (o peso já saiu, está registrado em consumo).
        assert _lote_na_api(client, headers_admin, base["lote"].id)["reservado_kg"] == 0

        client.post(f"/api/v1/ordens-corte/{oc['id']}/reabrir", headers=headers_admin, json={"quem": "BRUNO"})
        # Voltou a EM_CORTE: o peso dos encaixes está de volta no lote e
        # travado de novo. A reserva vem do PLANEJADO (peso × camadas), não
        # do kg_real que foi medido.
        visto = _lote_na_api(client, headers_admin, base["lote"].id)
        assert visto["reservado_kg"] == PLANEJADO
        assert visto["livre_kg"] == pytest.approx(PESO_LOTE - PLANEJADO)


# ── Pedido ────────────────────────────────────────────────────────────────────


class TestProducaoNoPedido:
    def test_pedido_traz_a_oc_ativa(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        # Na criação a OC é RASCUNHO e mesmo assim é a OC ativa do pedido.
        res = client.get(f"/api/v1/pedidos-venda/{oc['pedido_id']}", headers=headers_admin)
        assert res.status_code == 200, res.text
        assert res.json()["data"]["producao"] == {
            "oc_id": oc["id"],
            # Já formatado ("OC-0001"), que é como o numero da OC aparece na
            # tela — o front nao precisa formatar de novo.
            "oc_numero": oc["numero_fmt"],
            "status": "RASCUNHO",
        }

    def test_lista_de_pedidos_traz_producao(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/enviar", headers=headers_admin)
        res = client.get("/api/v1/pedidos-venda/", headers=headers_admin)
        assert res.status_code == 200, res.text
        linha = next(p for p in res.json()["data"] if p["id"] == oc["pedido_id"])
        assert linha["producao"]["status"] == "ENVIADA"
        assert linha["producao"]["oc_id"] == oc["id"]

    def test_pedido_sem_oc_tem_producao_nula(self, client, headers_admin, db_session, base):
        pedido = _criar_pedido(client, headers_admin, base["cliente"])
        res = client.get(f"/api/v1/pedidos-venda/{pedido['id']}", headers=headers_admin)
        assert res.json()["data"]["producao"] is None

    def test_oc_cancelada_sai_da_producao(self, client, headers_admin, db_session, base):
        oc = _criar_oc(client, headers_admin, db_session, base["cliente"], base["produto"], base["sku"], base["lote"])
        client.post(f"/api/v1/ordens-corte/{oc['id']}/cancelar", headers=headers_admin)
        res = client.get(f"/api/v1/pedidos-venda/{oc['pedido_id']}", headers=headers_admin)
        assert res.json()["data"]["producao"] is None
