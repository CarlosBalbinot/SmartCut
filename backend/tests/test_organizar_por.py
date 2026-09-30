"""PC1 — organizar a Ordem de Corte por PRODUTO ou por COR (Passos 1 e 3).

COR é o comportamento de sempre: tudo o que usa o mesmo lote entra no mesmo
risco (nesting_service._agrupar_por_lote, _montar_todos). PRODUTO é o plano de
corte por produto (_montar_plano_corte): cores do mesmo modelo de tecido
dividem o enfesto, o motor roda uma vez por risco e cada encaixe guarda as
camadas de cada cor em encaixe_camadas — é por elas que o estoque de cada
lote é reservado, planejado e baixado.

Os de ponta a ponta rodam o motor de verdade (spyrrow, perfil RÁPIDO) com
peças pequenas, sem gravar nada.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from models.encaixe import Encaixe, EncaixeCamada
from models.grupo_molde import GrupoMolde
from models.ordem_corte import ORGANIZAR_POR_PADRAO, OrdemCorte
from models.produto import GrupoProduto, Produto
from models.tecido import CorTecido, LoteTecido, ModeloTecido
from services import nesting_service as svc
from services import ordem_corte_service as ocs
from services.gramatura_service import metros_para_peso
from tests.test_decisor_enfesto import RETANGULO, _molde
from tests.test_ordem_corte_producao import _criar_oc, _novo_lote, _novo_produto


def _modelo(db, nome="MAXXI", max_camadas=15) -> ModeloTecido:
    m = ModeloTecido(nome=nome, tipo="Malha", max_camadas=max_camadas)
    db.add(m)
    db.commit()
    return m


def _lote_de(db, modelo, cor="PRETO", largura=150.0, gramatura=200.0, peso=50.0) -> LoteTecido:
    c = CorTecido(
        modelo_id=modelo.id, nome_cor=cor, largura_util_cm=largura, gramatura_g_m2=gramatura, encolhimento_pct=0.0
    )
    db.add(c)
    db.commit()
    lote = LoteTecido(
        cor_id=c.id,
        codigo_lote=f"L{uuid.uuid4().hex[:6]}",
        peso_inicial_kg=peso,
        peso_disponivel_kg=peso,
        valor_kg=30.0,
        data_compra=date(2026, 1, 1),
    )
    db.add(lote)
    db.commit()
    db.refresh(lote)
    return lote


def _produto(db, descricao: str) -> Produto:
    grupo_produto = GrupoProduto(codigo=f"G{uuid.uuid4().hex[:5]}", nome="FEMININO", prefixo="FEM")
    db.add(grupo_produto)
    db.commit()
    produto = Produto(grupo_id=grupo_produto.id, codigo=f"P{uuid.uuid4().hex[:6]}", descricao=descricao, unidade="UN")
    db.add(produto)
    db.commit()
    return produto


def _moldes_do_produto(db, produto: Produto, pecas: list[str], tamanho="M") -> list:
    grupo = GrupoMolde(nome=produto.descricao, produto_id=produto.id)
    db.add(grupo)
    db.commit()
    moldes = []
    for peca in pecas:
        m = _molde(db, peca, RETANGULO, "simples")
        m.grupo_id = grupo.id
        m.tamanho = tamanho
        db.commit()
        db.refresh(m)
        moldes.append(m)
    return moldes


def _cenario(db):
    """Dois produtos (LEGGING com 2 partes, TOP com 1) e duas cores do mesmo
    tecido (PRETO 150 cm, MARROM 146 cm)."""
    maxxi = _modelo(db)
    preto = _lote_de(db, maxxi, "PRETO", 150.0)
    marrom = _lote_de(db, maxxi, "MARROM", 146.0, gramatura=210.0)
    legging = _produto(db, "LEGGING")
    top = _produto(db, "TOP")
    m_legging = _moldes_do_produto(db, legging, ["FRENTE", "COSTAS"])
    m_top = _moldes_do_produto(db, top, ["FRENTE"])
    entradas = (
        [(preto, m, 3) for m in m_legging]
        + [(marrom, m, 3) for m in m_legging]
        + [(preto, m, 2) for m in m_top]
        + [(marrom, m, 1) for m in m_top]
    )
    return {"preto": preto, "marrom": marrom, "legging": legging, "top": top, "entradas": entradas}


class _DbFalso:
    def rollback(self):
        pass


# ── Agrupamento do plano (puro) ─────────────────────────────────────────────


def test_produto_agrupa_por_produto_e_modelo_de_tecido(db_session):
    c = _cenario(db_session)
    grupos = svc._agrupar_produto(c["entradas"])
    assert sorted(g.produto_nome for g in grupos.values()) == ["LEGGING", "TOP"]
    for g in grupos.values():
        # PRETO 150 e MARROM 146: mesmo modelo, até 5 cm — o mesmo grupo
        assert {x.nome for x in g.cores} == {"PRETO", "MARROM"}
    top = next(g for g in grupos.values() if g.produto_nome == "TOP")
    assert {x.nome: x.grade for x in top.cores} == {"PRETO": {"M": 2}, "MARROM": {"M": 1}}


def test_outro_modelo_de_tecido_e_outro_grupo(db_session):
    legging = _produto(db_session, "LEGGING")
    (frente,) = _moldes_do_produto(db_session, legging, ["FRENTE"])
    maxxi, canelado = _modelo(db_session), _modelo(db_session, "CANELADO", 10)
    a, b = _lote_de(db_session, maxxi), _lote_de(db_session, canelado, "VERDE", 130.0)
    grupos = svc._agrupar_produto([(a, frente, 2), (b, frente, 2)])
    assert len(grupos) == 2


# ── Ponta a ponta (motor de verdade, sem gravar) ─────────────────────────


def test_por_cor_e_o_fluxo_de_sempre(db_session, monkeypatch):
    c = _cenario(db_session)
    monkeypatch.setattr(svc, "_gravar", lambda db, encaixes: None)
    capturados = []
    original = svc._montar_todos

    def _espia(*a, **kw):
        r = original(*a, **kw)
        capturados.extend(r[0])
        return r

    monkeypatch.setattr(svc, "_montar_todos", _espia)
    r = svc.gerar_de_entradas(_DbFalso(), None, c["entradas"], qualidade="RAPIDO", organizar_por="COR")
    assert {d["grupo"] for d in r["decisoes"]} == {str(c["preto"].id), str(c["marrom"].id)}
    assert all(d["grupo"] == d["lote_id"] for d in r["decisoes"])
    assert capturados and all(not e.camadas_cor for e in capturados)
    # por cor, LEGGING e TOP do mesmo lote vão no mesmo risco
    assert any(len({p["grupo_nome"] for p in e.mapa_json["placements"]}) == 2 for e in capturados)


def test_por_produto_enfesto_multicor_e_estoque_por_lote(db_session, monkeypatch):
    c = _cenario(db_session)
    capturados = []
    monkeypatch.setattr(svc, "_gravar", lambda db, encaixes: capturados.extend(encaixes))
    r = svc.gerar_de_entradas(_DbFalso(), None, c["entradas"], qualidade="RAPIDO", organizar_por="PRODUTO")

    assert sorted(d["produto_nome"] for d in r["decisoes"]) == ["LEGGING", "TOP"]
    for d in r["decisoes"]:
        assert d["modo_camadas"] == "PLANO_CORTE"
        assert set(d["lotes"]) == {str(c["preto"].id), str(c["marrom"].id)}
        assert "Plano de corte:" in d["motivo"]
    assert capturados and all(e.camadas_cor for e in capturados)
    for e in capturados:
        # um risco nunca mistura produtos
        assert len({p["grupo_nome"] for p in e.mapa_json["placements"]}) == 1
        assert sum(x.camadas for x in e.camadas_cor) == e.num_camadas
        # cada lote pelo tecido dele: peso de uma camada = metros × gramatura × largura do lote
        for x in e.camadas_cor:
            lote = c["preto"] if x.lote_id == c["preto"].id else c["marrom"]
            esperado = metros_para_peso(
                float(x.comp_metros), float(lote.cor.gramatura_g_m2), float(lote.cor.largura_util_cm)
            )
            assert float(x.peso_kg) == pytest.approx(esperado, abs=0.001)
        # o total do encaixe (média × camadas) bate com a soma das cores
        assert float(e.peso_kg) * e.num_camadas == pytest.approx(sum(e.consumo_por_lote().values()), abs=0.01)

    # peças cortadas por cor = pedido (nenhuma cor falta, sem sobra no simples)
    cortado: dict[tuple, int] = {}
    for e in capturados:
        for x in e.camadas_cor:
            for linha in e.mapa_json["pecas_parte"]:
                k = (x.cor, linha["grupo_nome"], linha["molde"])
                cortado[k] = cortado.get(k, 0) + linha["por_camada"] * x.camadas
    assert cortado[("PRETO", "LEGGING", "FRENTE")] >= 3 and cortado[("MARROM", "LEGGING", "COSTAS")] >= 3
    assert cortado[("PRETO", "TOP", "FRENTE")] >= 2 and cortado[("MARROM", "TOP", "FRENTE")] >= 1
    assert sum(p["sobra_total"] for p in r["planos"].values()) == 0


# ── Estoque da OC com encaixe multicor ──────────────────────────────────────


def _encaixe_multicor(db, oc_id, pedido_id, lotes_camadas):
    e = Encaixe(
        pedido_id=pedido_id,
        ordem_corte_id=oc_id,
        lote_id=lotes_camadas[0][0].id,
        numero=1000 + (db.query(Encaixe).count() or 0),
        comp_metros=Decimal("2.000"),
        peso_kg=Decimal("0.500"),
        num_camadas=sum(n for _, n, _ in lotes_camadas),
        status="ativo",
        mapa_json={"multicor": True},
    )
    e.camadas_cor = [
        EncaixeCamada(lote_id=lote.id, ordem=i, cor=lote.cor.nome_cor, camadas=n, peso_kg=Decimal(str(kg)))
        for i, (lote, n, kg) in enumerate(lotes_camadas)
    ]
    db.add(e)
    db.commit()
    return e


def test_estoque_multicor_reserva_e_baixa_cada_lote(client, headers_admin, db_session, cliente):
    lote_a = _novo_lote(db_session, "LOTE-A")
    produto, sku = _novo_produto(db_session)
    oc = _criar_oc(client, headers_admin, db_session, cliente, produto, sku, lote_a)
    oc_id = uuid.UUID(oc["id"])
    lote_b = _novo_lote(db_session, "LOTE-B")
    # o encaixe "de um lote só" que _criar_oc gravou (2 kg × 3 camadas no A) +
    # um multicor: A 4 camadas × 0,5 kg, B 6 camadas × 0,6 kg
    _encaixe_multicor(db_session, oc_id, uuid.UUID(oc["pedido_id"]), [(lote_a, 4, 0.5), (lote_b, 6, 0.6)])

    ocm = db_session.get(OrdemCorte, oc_id)
    db_session.refresh(ocm)
    planejado = ocs._consumo_por_lote(ocm.encaixes)
    assert planejado[lote_a.id] == pytest.approx(6.0 + 2.0)
    assert planejado[lote_b.id] == pytest.approx(3.6)

    ocm.status = "ENVIADA"
    db_session.commit()
    reservas = ocs.reservas_kg(db_session)
    # o lote principal do multicor (A) NÃO leva o peso do B
    assert reservas[lote_a.id] == pytest.approx(8.0)
    assert reservas[lote_b.id] == pytest.approx(3.6)

    ocm.status = "EM_CORTE"
    db_session.commit()
    ocs.concluir(db_session, oc_id, "ANA", [])
    db_session.expire_all()
    assert float(db_session.get(LoteTecido, lote_a.id).peso_disponivel_kg) == pytest.approx(50.0 - 8.0)
    assert float(db_session.get(LoteTecido, lote_b.id).peso_disponivel_kg) == pytest.approx(50.0 - 3.6)


# ── A OC ─────────────────────────────────────────────────────────────────


def test_oc_nova_e_por_produto_e_troca_para_cor(client, headers_admin, db_session, cliente):
    lote = _novo_lote(db_session)
    produto, sku = _novo_produto(db_session)
    oc = _criar_oc(client, headers_admin, db_session, cliente, produto, sku, lote)
    assert ORGANIZAR_POR_PADRAO == "PRODUTO"
    assert oc["organizar_por"] == "PRODUTO"

    res = client.put(f"/api/v1/ordens-corte/{oc['id']}", headers=headers_admin, json={"organizar_por": "COR"})
    assert res.status_code == 200, res.text
    assert res.json()["data"]["organizar_por"] == "COR"
    assert db_session.get(OrdemCorte, uuid.UUID(oc["id"])).organizar_por == "COR"

    res = client.put(f"/api/v1/ordens-corte/{oc['id']}", headers=headers_admin, json={"organizar_por": "TAMANHO"})
    assert res.status_code == 422
