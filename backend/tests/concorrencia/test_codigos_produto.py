"""Códigos de grupo, produto e SKU pela sequência atômica (F0, passo 1d).

Antes, cada service lia todos os códigos e calculava o maior em Python: duas
criações ao mesmo tempo pegavam o mesmo código e a segunda quebrava na UNIQUE.
"""

from models.produto import GrupoProduto
from models.tabela_grade import ItemTabelaGrade, TabelaGrade
from schemas.produto_schema import GrupoProdutoCreate, ProdutoCreate
from services import grupo_produto_service, produto_service, sku_service
from tests.concorrencia.disputa import disputar, erros

N = 8


def _grupo(fabrica, prefixo="GT", codigo=None):
    db = fabrica()
    try:
        if codigo:  # grupo "antigo", gravado com código fixo
            grupo = GrupoProduto(codigo=codigo, nome=f"GRUPO {codigo}", prefixo=prefixo)
            db.add(grupo)
            db.commit()
        else:
            grupo = grupo_produto_service.criar(db, GrupoProdutoCreate(nome="GRUPO", prefixo=prefixo))
        return grupo.id
    finally:
        db.close()


def _produto(db, grupo_id):
    return produto_service.criar(db, ProdutoCreate(grupo_id=grupo_id, descricao="CAMISETA", unidade="UN"))


def _grade(fabrica) -> list[dict]:
    """Uma cor × dois tamanhos: as mesmas combinações para todos os produtos."""
    db = fabrica()
    try:
        grade = TabelaGrade(codigo="TG1", descricao="GRADE", situacao="Ativa")
        db.add(grade)
        db.flush()
        cor = ItemTabelaGrade(tabela_id=grade.id, codigo_curto="AZ", descricao="Azul", ordem=1, situacao="Ativa")
        p = ItemTabelaGrade(tabela_id=grade.id, codigo_curto="P", descricao="P", ordem=1, situacao="Ativa")
        m = ItemTabelaGrade(tabela_id=grade.id, codigo_curto="M", descricao="M", ordem=2, situacao="Ativa")
        db.add_all([cor, p, m])
        db.commit()
        return [{"linha_item_id": cor.id, "coluna_item_id": t.id} for t in (p, m)]
    finally:
        db.close()


def test_grupos_criados_ao_mesmo_tempo(fabrica_sessao):
    res = disputar(
        fabrica_sessao,
        N,
        lambda sessao, i: grupo_produto_service.criar(sessao, GrupoProdutoCreate(nome=f"G{i}", prefixo="X")).codigo,
    )
    assert not erros(res), erros(res)
    assert sorted(r.valor for r in res) == [f"{n:03d}" for n in range(1, N + 1)]


def test_produtos_do_mesmo_grupo_ao_mesmo_tempo(fabrica_sessao):
    grupo_id = _grupo(fabrica_sessao)
    res = disputar(fabrica_sessao, N, lambda sessao, i: _produto(sessao, grupo_id).codigo)
    assert not erros(res), erros(res)
    assert sorted(r.valor for r in res) == [f"GT-{n:03d}" for n in range(1, N + 1)]


def test_grupos_com_o_mesmo_prefixo_nao_repetem_codigo(fabrica_sessao):
    # O prefixo não é único entre grupos; o código do produto é único no
    # banco inteiro. Antes, cada grupo contava só os seus: os dois davam GT-001.
    grupos = [_grupo(fabrica_sessao, codigo="901"), _grupo(fabrica_sessao, codigo="902")]
    res = disputar(fabrica_sessao, N, lambda sessao, i: _produto(sessao, grupos[i % 2]).codigo)
    assert not erros(res), erros(res)
    assert sorted(r.valor for r in res) == [f"GT-{n:03d}" for n in range(1, N + 1)]


def test_skus_gerados_ao_mesmo_tempo(fabrica_sessao):
    # Produtos do mesmo prefixo gerando as MESMAS combinações de grade ao
    # mesmo tempo: antes, todos partiam do mesmo {SEQ} e colidiam.
    grupo_id = _grupo(fabrica_sessao)
    combos = _grade(fabrica_sessao)
    db = fabrica_sessao()
    try:
        produtos = [_produto(db, grupo_id).id for _ in range(N)]
    finally:
        db.close()

    res = disputar(
        fabrica_sessao, N, lambda sessao, i: [s.codigo for s in sku_service.gerar_skus(sessao, produtos[i], combos)]
    )
    assert not erros(res), erros(res)
    codigos = [c for r in res for c in r.valor]
    assert len(codigos) == len(set(codigos)) == 2 * N
