"""PC1 · Passo 1 — organizar a Ordem de Corte por PRODUTO ou por COR.

COR é o comportamento de sempre: tudo o que usa o mesmo lote entra no mesmo
risco (nesting_service._agrupar_por_lote). PRODUTO separa por (lote, produto):
um risco nunca mistura produtos. Os de ponta a ponta rodam o motor de verdade
(spyrrow, perfil RÁPIDO) com peças pequenas, sem gravar nada.
"""

import uuid

from models.grupo_molde import GrupoMolde
from models.ordem_corte import ORGANIZAR_POR_PADRAO, OrdemCorte
from models.produto import GrupoProduto, Produto
from services import nesting_service as svc
from tests.test_decisor_enfesto import RETANGULO, _lote, _molde
from tests.test_ordem_corte_producao import _criar_oc, _novo_lote, _novo_produto


def _produto(db, descricao: str) -> Produto:
    grupo_produto = GrupoProduto(codigo=f"G{uuid.uuid4().hex[:5]}", nome="FEMININO", prefixo="FEM")
    db.add(grupo_produto)
    db.commit()
    produto = Produto(grupo_id=grupo_produto.id, codigo=f"P{uuid.uuid4().hex[:6]}", descricao=descricao, unidade="UN")
    db.add(produto)
    db.commit()
    return produto


def _moldes_do_produto(db, produto: Produto, pecas: list[str]) -> list:
    grupo = GrupoMolde(nome=produto.descricao, produto_id=produto.id)
    db.add(grupo)
    db.commit()
    moldes = []
    for peca in pecas:
        m = _molde(db, peca, RETANGULO, "simples")
        m.grupo_id = grupo.id
        db.commit()
        db.refresh(m)
        moldes.append(m)
    return moldes


def _cenario(db):
    """Um lote, dois produtos (LEGGING com 2 partes, TOP com 1)."""
    lote = _lote(db)
    legging = _produto(db, "LEGGING")
    top = _produto(db, "TOP")
    m_legging = _moldes_do_produto(db, legging, ["FRENTE", "COSTAS"])
    m_top = _moldes_do_produto(db, top, ["FRENTE"])
    entradas = [(lote, m, 2) for m in m_legging] + [(lote, m, 2) for m in m_top]
    return lote, legging, top, m_legging, m_top, entradas


# ── Agrupamento (puro) ────────────────────────────────────────────────────


def test_cor_e_o_agrupamento_de_sempre(db_session):
    lote, _, _, _, _, entradas = _cenario(db_session)
    por_cor = svc._agrupar(entradas, "COR")
    antigo = svc._agrupar_por_lote(entradas)
    assert list(por_cor) == list(antigo) == [lote.id]
    assert {k: q for k, (_, q) in por_cor[lote.id][1].items()} == {k: q for k, (_, q) in antigo[lote.id][1].items()}


def test_produto_separa_os_produtos_do_mesmo_lote(db_session):
    lote, legging, top, m_legging, m_top, entradas = _cenario(db_session)
    grupos = svc._agrupar(entradas, "PRODUTO")
    assert list(grupos) == [f"{lote.id}:{legging.id}", f"{lote.id}:{top.id}"]
    assert set(grupos[f"{lote.id}:{legging.id}"][1]) == {m.id for m in m_legging}
    assert set(grupos[f"{lote.id}:{top.id}"][1]) == {m.id for m in m_top}
    # o lote de verdade continua no tecido do grupo
    assert all(t.lote_id == lote.id for t, _ in grupos.values())


def test_produto_em_dois_lotes_sao_dois_grupos(db_session):
    preto, branco = _lote(db_session), _lote(db_session)
    legging = _produto(db_session, "LEGGING")
    (frente,) = _moldes_do_produto(db_session, legging, ["FRENTE"])
    grupos = svc._agrupar([(preto, frente, 2), (branco, frente, 3)], "PRODUTO")
    assert list(grupos) == [f"{preto.id}:{legging.id}", f"{branco.id}:{legging.id}"]


# ── Ponta a ponta (motor de verdade, sem gravar) ─────────────────────────


def test_ponta_a_ponta_por_produto_nao_mistura_produtos(db_session):
    lote, legging, top, m_legging, m_top, entradas = _cenario(db_session)
    grupos = svc._agrupar(entradas, "PRODUTO")
    encaixes, _, planos, decisoes = svc._montar_todos(None, grupos, "AUTOMATICO", None, None, 150, "RAPIDO", None)
    assert set(decisoes) == set(planos) == set(grupos)
    ids_legging = {str(m.id) for m in m_legging}
    ids_top = {str(m.id) for m in m_top}
    for e in encaixes:
        ids = {p["id"] for p in e.mapa_json["placements"]}
        assert ids <= ids_legging or ids <= ids_top  # nunca os dois produtos
        assert e.lote_id == lote.id
        esperado = legging if ids <= ids_legging else top
        assert e.mapa_json["grupo_corte"] == f"{lote.id}:{esperado.id}"
        assert e.mapa_json["produto_nome"] == esperado.descricao


def test_ponta_a_ponta_por_cor_nao_grava_grupo(db_session):
    lote, _, _, m_legging, m_top, entradas = _cenario(db_session)
    grupos = svc._agrupar(entradas, "COR")
    encaixes, _, _, decisoes = svc._montar_todos(None, grupos, "AUTOMATICO", None, None, 150, "RAPIDO", None)
    assert list(decisoes) == [str(lote.id)]
    assert encaixes
    for e in encaixes:
        assert "grupo_corte" not in e.mapa_json and "produto_nome" not in e.mapa_json
    todos = {p["id"] for e in encaixes for p in e.mapa_json["placements"]}
    assert todos == {str(m.id) for m in m_legging + m_top}  # os dois produtos no mesmo risco


class _DbFalso:
    def rollback(self):
        pass


def test_decisoes_de_saida_levam_grupo_e_lote(db_session, monkeypatch):
    lote, legging, top, _, _, entradas = _cenario(db_session)
    monkeypatch.setattr(svc, "_gravar", lambda db, encaixes: None)
    r = svc.gerar_de_entradas(_DbFalso(), None, entradas, qualidade="RAPIDO", organizar_por="PRODUTO")
    assert {d["grupo"] for d in r["decisoes"]} == {f"{lote.id}:{legging.id}", f"{lote.id}:{top.id}"}
    assert {d["lote_id"] for d in r["decisoes"]} == {str(lote.id)}
    assert {d["produto_nome"] for d in r["decisoes"]} == {"LEGGING", "TOP"}
    assert {e["grupo_corte"] for e in r["encaixes"]} == {d["grupo"] for d in r["decisoes"]}

    r_cor = svc.gerar_de_entradas(_DbFalso(), None, entradas, qualidade="RAPIDO", organizar_por="COR")
    (d,) = r_cor["decisoes"]
    assert d["grupo"] == d["lote_id"] == str(lote.id)
    assert "produto_nome" not in d
    assert all(e["grupo_corte"] is None for e in r_cor["encaixes"])


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
