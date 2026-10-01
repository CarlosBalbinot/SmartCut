"""Sequências atômicas sob disputa (F0, passo 1a): sessões ao mesmo tempo
nunca recebem o mesmo número."""

from services import sequencia_service as seq
from tests.concorrencia.disputa import disputar, erros

N = 20


def test_proximo_em_paralelo_nao_repete(fabrica_sessao):
    def fn(sessao, i):
        valor = seq.proximo(sessao, "oc")
        sessao.commit()
        return valor

    res = disputar(fabrica_sessao, N, fn)
    assert not erros(res)
    assert sorted(r.valor for r in res) == list(range(1, N + 1))


def test_criacao_da_sequencia_em_paralelo(fabrica_sessao):
    # Todas as sessões encontram a sequência inexistente e tentam criá-la
    # juntas: uma cria, as outras ignoram, e ninguém repete número.
    def fn(sessao, i):
        valor = seq.proximo(sessao, "encaixe", lambda db: 100)
        sessao.commit()
        return valor

    res = disputar(fabrica_sessao, N, fn)
    assert not erros(res)
    assert sorted(r.valor for r in res) == list(range(101, 101 + N))


def test_numero_de_transacao_desfeita_volta(fabrica_sessao):
    # Metade das sessões desfaz a transação: os números entregues no fim
    # continuam sem repetição e sem buraco.
    def fn(sessao, i):
        valor = seq.proximo(sessao, "oc")
        if i % 2:
            sessao.rollback()
            return None
        sessao.commit()
        return valor

    res = disputar(fabrica_sessao, N, fn)
    assert not erros(res)
    entregues = sorted(r.valor for r in res if r.valor is not None)
    assert entregues == list(range(1, N // 2 + 1))


def test_garantir_minimo_em_paralelo_com_proximo(fabrica_sessao):
    # Código digitado à mão (garantir_minimo 50) disputando com numerações
    # automáticas: nenhum número automático depois dele fica <= 50 e nada repete.
    def fn(sessao, i):
        if i == 0:
            seq.garantir_minimo(sessao, "grupo_produto", 50)
            sessao.commit()
            return None
        valor = seq.proximo(sessao, "grupo_produto")
        sessao.commit()
        return valor

    res = disputar(fabrica_sessao, N, fn)
    assert not erros(res)
    valores = [r.valor for r in res if r.valor is not None]
    assert len(set(valores)) == len(valores) == N - 1
    assert 50 not in valores
    sessao = fabrica_sessao()
    try:
        assert seq.atual(sessao, "grupo_produto") == max(max(valores), 50)
    finally:
        sessao.close()
