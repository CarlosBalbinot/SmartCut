"""Códigos de grupo, produto e SKU (F0, passo 1d): ponto de partida das
sequências, troca de grupo, códigos antigos e código de SKU digitado à mão.

A disputa entre sessões fica em tests/concorrencia/test_codigos_produto.py.
"""

from models.produto import GrupoProduto, Produto
from models.produto_sku import ProdutoSKU
from models.tabela_grade import ItemTabelaGrade, TabelaGrade
from schemas.produto_schema import GrupoProdutoCreate, ProdutoCreate, ProdutoUpdate
from services import grade_service, grupo_produto_service, produto_service, sku_service


def _grupo(db, prefixo="GT", codigo=None) -> GrupoProduto:
    if codigo:
        grupo = GrupoProduto(codigo=codigo, nome=f"GRUPO {codigo}", prefixo=prefixo)
        db.add(grupo)
        db.commit()
        return grupo
    return grupo_produto_service.criar(db, GrupoProdutoCreate(nome="GRUPO", prefixo=prefixo))


def _produto(db, grupo) -> Produto:
    return produto_service.criar(db, ProdutoCreate(grupo_id=grupo.id, descricao="CAMISETA", unidade="UN"))


def _combos(db, tamanhos=("P", "M")) -> list[dict]:
    grade = TabelaGrade(codigo="TG1", descricao="GRADE", situacao="Ativa")
    db.add(grade)
    db.flush()
    cor = ItemTabelaGrade(tabela_id=grade.id, codigo_curto="AZ", descricao="Azul", ordem=1, situacao="Ativa")
    itens = [
        ItemTabelaGrade(tabela_id=grade.id, codigo_curto=t, descricao=t, ordem=i, situacao="Ativa")
        for i, t in enumerate(tamanhos, start=1)
    ]
    db.add_all([cor, *itens])
    db.commit()
    return [{"linha_item_id": cor.id, "coluna_item_id": t.id} for t in itens]


# ── Grupo ─────────────────────────────────────────────────────────────────────


def test_grupo_continua_do_maior_codigo_numerico(db_session):
    _grupo(db_session, codigo="007")
    _grupo(db_session, codigo="ABC")  # não numérico: ignorado, como antes
    assert _grupo(db_session).codigo == "008"
    assert _grupo(db_session).codigo == "009"


# ── Produto ───────────────────────────────────────────────────────────────────


def test_produto_continua_do_maior_codigo_do_prefixo(db_session):
    grupo = _grupo(db_session)
    db_session.add(Produto(grupo_id=grupo.id, codigo="GT-012", descricao="ANTIGO", unidade="UN"))
    db_session.commit()
    assert _produto(db_session, grupo).codigo == "GT-013"


def test_produto_que_muda_de_grupo_usa_a_sequencia_do_grupo_novo(db_session):
    origem, destino = _grupo(db_session, "AA"), _grupo(db_session, "BB")
    _produto(db_session, destino)  # BB-001
    produto = _produto(db_session, origem)  # AA-001
    atualizado = produto_service.atualizar(db_session, produto.id, ProdutoUpdate(grupo_id=destino.id))
    assert atualizado.codigo == "BB-002"
    # A sequência do grupo novo andou; a do antigo não volta atrás.
    assert _produto(db_session, destino).codigo == "BB-003"
    assert _produto(db_session, origem).codigo == "AA-002"


# ── SKU ───────────────────────────────────────────────────────────────────────


def test_skus_seguem_a_sequencia_do_prefixo(db_session):
    grupo = _grupo(db_session)
    combos = _combos(db_session)
    a, b = _produto(db_session, grupo), _produto(db_session, grupo)  # GT-001, GT-002
    # Máscara padrão {GRUPO}-{SEQ}-{COR}-{TAM}, SEQ com 4 dígitos; a
    # sequência começa depois do maior produto (regra antiga): 0003.
    assert [s.codigo for s in sku_service.gerar_skus(db_session, a.id, combos)] == ["GT-0003-AZ-P", "GT-0004-AZ-M"]
    # Antes: o produto B recomeçava em 0003 (mesma cor/tamanho → mesmo código).
    assert [s.codigo for s in sku_service.gerar_skus(db_session, b.id, combos)] == ["GT-0005-AZ-P", "GT-0006-AZ-M"]


def test_sku_pula_codigo_que_ja_existe(db_session):
    grupo = _grupo(db_session)
    combos = _combos(db_session)
    a, b = _produto(db_session, grupo), _produto(db_session, grupo)
    # SKU antigo (regra anterior) que já ocupa o próximo código.
    db_session.add(ProdutoSKU(produto_pai_id=a.id, codigo="GT-0003-AZ-P"))
    db_session.commit()
    assert [s.codigo for s in sku_service.gerar_skus(db_session, b.id, combos)] == ["GT-0004-AZ-P", "GT-0005-AZ-M"]


def test_codigo_de_sku_digitado_a_mao_sobe_a_sequencia(client, headers_admin, db_session):
    grupo = _grupo(db_session)
    combos = _combos(db_session, ("P", "M", "G"))
    produto = _produto(db_session, grupo)  # GT-001
    (sku,) = sku_service.gerar_skus(db_session, produto.id, combos[:1])  # GT-0002-AZ-P

    res = client.patch(
        f"/api/v1/produtos/{produto.id}/skus/{sku.id}", headers=headers_admin, json={"codigo": "GT-0050-AZ-P"}
    )
    assert res.status_code == 200, res.text
    db_session.expire_all()
    novos = sku_service.gerar_skus(db_session, produto.id, combos[1:])
    assert [s.codigo for s in novos] == ["GT-0051-AZ-M", "GT-0052-AZ-G"]


def test_seq_do_codigo_com_e_sem_separador(db_session):
    assert grade_service.seq_do_codigo(db_session, "GT", "GT-0050-AZ-P") == 50
    assert grade_service.seq_do_codigo(db_session, "GT", "QUALQUER") is None
    config = grade_service.obter_configuracao(db_session)
    config.mascara, config.separador = "{GRUPO}{SEQ}{COR}{TAM}", ""
    db_session.commit()
    assert grade_service.seq_do_codigo(db_session, "LEG", "LEG0002002001") == 2
