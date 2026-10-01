"""Testes da própria base de concorrência: as threads disputam de verdade,
cada uma com a sua conexão, e nenhum erro se perde."""

import threading

import pytest
from sqlalchemy import text

from tests.concorrencia.disputa import disputar, erros

N = 8


def test_threads_ficam_dentro_de_fn_ao_mesmo_tempo(fabrica_sessao):
    # Se as chamadas fossem em série, a barreira interna nunca completaria.
    dentro = threading.Barrier(N, timeout=10)

    def fn(sessao, i):
        dentro.wait()
        return threading.get_ident()

    res = disputar(fabrica_sessao, N, fn)
    assert not erros(res)
    assert len({r.valor for r in res}) == N


def test_cada_thread_tem_a_sua_conexao(fabrica_sessao):
    dentro = threading.Barrier(N, timeout=10)

    def fn(sessao, i):
        bruta = sessao.connection().connection.dbapi_connection
        dentro.wait()  # todas seguram a conexão ao mesmo tempo
        return id(bruta)

    res = disputar(fabrica_sessao, N, fn)
    assert not erros(res)
    assert len({r.valor for r in res}) == N


def test_erro_de_uma_thread_fica_no_resultado(fabrica_sessao):
    def fn(sessao, i):
        if i % 2:
            raise ValueError(f"falha {i}")
        return i

    res = disputar(fabrica_sessao, 4, fn)
    assert [r.ok for r in res] == [True, False, True, False]
    assert str(res[1].erro) == "falha 1"
    assert res[2].valor == 2


def test_gravacoes_disputadas_nao_se_perdem(engine_concorrente, fabrica_sessao):
    # UPDATE com a conta no SQL, em transações concorrentes: a configuração
    # do engine do app espera a vez em vez de falhar com "database is locked".
    with engine_concorrente.begin() as conn:
        conn.execute(text("create table contador_teste (id integer primary key, valor integer not null)"))
        conn.execute(text("insert into contador_teste (id, valor) values (1, 0)"))

    def fn(sessao, i):
        sessao.execute(text("update contador_teste set valor = valor + 1 where id = 1"))
        sessao.commit()

    try:
        res = disputar(fabrica_sessao, N, fn)
        assert not erros(res)
        with engine_concorrente.connect() as conn:
            assert conn.execute(text("select valor from contador_teste where id = 1")).scalar_one() == N
    finally:
        with engine_concorrente.begin() as conn:
            conn.execute(text("drop table contador_teste"))


def test_thread_presa_falha_o_teste(fabrica_sessao):
    nunca = threading.Event()

    with pytest.raises(AssertionError, match="não terminaram"):
        disputar(fabrica_sessao, 2, lambda sessao, i: nunca.wait(), timeout=0.5)
    nunca.set()
