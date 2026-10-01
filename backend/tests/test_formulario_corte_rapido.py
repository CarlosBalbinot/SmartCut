"""relPro001 do Encaixe Rápido: sem OC, pelo id do pedido do encaixe.

Os encaixes são gravados direto no banco (mesmo formato do motor). O modelo
renderizado é o da pasta relatorios/ do repositório (só leitura).
"""

import uuid
from decimal import Decimal

from models.encaixe import Encaixe
from services.relatorios import dados_ordem_corte
from tests.test_ordem_corte_producao import _novo_lote
from tests.test_pedidos_precificacao import _criar_pedido

MAPA = {
    "largura_cm": 150.0,
    "comprimento_cm": 87.0,
    "comprimento_max_cm": 120,
    "enfesto": 1,
    "tipo_enfesto": "FACE_A_FACE",
    "placements": [
        {
            "id": "m1",
            "x": 0.0,
            "y": 0.0,
            "rotation": 0,
            "polygon": [[0, 0], [40, 0], [40, 80], [0, 80]],
            "peca": "COSTAS",
            "tamanho": "M",
            "grupo_nome": "LEGGING",
        }
    ],
    "pecas_por_tamanho": [{"grupo_nome": "LEGGING", "tamanho": "M", "conjuntos": 1, "pecas": 4, "sobra": 0}],
}


def _encaixe(db, pedido_id, lote, numero, ordem_corte_id=None, status="ativo"):
    e = Encaixe(
        pedido_id=pedido_id,
        ordem_corte_id=ordem_corte_id,
        lote_id=lote.id,
        numero=numero,
        mapa_json=MAPA,
        comp_metros=Decimal("0.870"),
        peso_kg=Decimal("0.500"),
        num_camadas=4,
        status=status,
    )
    db.add(e)
    db.commit()
    return e


def test_contexto_do_encaixe_rapido(client, headers_admin, cliente, db_session):
    pedido = _criar_pedido(client, headers_admin, cliente)
    pedido_id = uuid.UUID(pedido["id"])
    lote = _novo_lote(db_session)
    _encaixe(db_session, pedido_id, lote, 901)
    _encaixe(db_session, pedido_id, lote, 902)
    _encaixe(db_session, pedido_id, lote, 903, status="deletado")

    ctx = dados_ordem_corte.montar(db_session, str(pedido_id))

    assert ctx["oc"]["numero"] == "Encaixe Rápido"
    assert ctx["oc"]["comprimento_max_cm"] == 120  # limite gravado no encaixe
    assert ctx["pedido"]["cliente"] == "CLIENTE LTDA"
    assert [m["numero_mesa"] for m in ctx["mesas"]] == [1, 2]  # deletado fica de fora
    assert ctx["mesas"][0]["enfesto_texto"] == "Enfesto duplo · 4 camadas"
    assert ctx["produtos"] == []
    assert ctx["totais"]["mesas"] == 2


def test_relpro001_renderiza_encaixe_rapido(client, headers_admin, cliente, db_session):
    pedido = _criar_pedido(client, headers_admin, cliente)
    lote = _novo_lote(db_session)
    _encaixe(db_session, uuid.UUID(pedido["id"]), lote, 911)

    res = client.get(f"/api/v1/relatorios/relPro001/html?id={pedido['id']}", headers=headers_admin)

    assert res.status_code == 200, res.text
    assert "FORMULÁRIO DE CORTE" in res.text
    assert "Encaixe Rápido" in res.text
    assert "COSTAS M" in res.text  # desenho da mesa


def test_relpro001_pedido_sem_encaixe_rapido_404(client, headers_admin, cliente):
    pedido = _criar_pedido(client, headers_admin, cliente)
    res = client.get(f"/api/v1/relatorios/relPro001/html?id={pedido['id']}", headers=headers_admin)
    assert res.status_code == 404
