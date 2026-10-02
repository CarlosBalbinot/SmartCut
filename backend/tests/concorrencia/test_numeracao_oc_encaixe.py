"""Números de OC e de encaixe pela sequência atômica (F0, passo 1c).

Antes: OC = MAX + 1 sem nova tentativa (a colisão virava 409 "Outra Ordem
de Corte foi criada ao mesmo tempo") e encaixe = MAX + 1 com 3 tentativas.
Agora as duas numerações saem de services/sequencia_service.py.
"""

import uuid
from decimal import Decimal

import pytest

from models.encaixe import Encaixe
from models.ordem_corte import OrdemCorte
from services import nesting_service
from services import ordem_corte_service as svc
from tests.concorrencia import cenario
from tests.concorrencia.disputa import disputar, erros

N = 10


def _pedidos(fabrica, n: int) -> list[uuid.UUID]:
    return cenario.pedidos(fabrica, n)


def _encaixe(pedido_id: uuid.UUID) -> Encaixe:
    return Encaixe(pedido_id=pedido_id, comp_metros=Decimal("2.000"), peso_kg=1.0, num_camadas=1, status="ativo")


def test_ocs_criadas_ao_mesmo_tempo_tem_numeros_unicos(fabrica_sessao):
    pedidos = _pedidos(fabrica_sessao, N)

    res = disputar(fabrica_sessao, N, lambda sessao, i: svc.criar_ordem_corte(sessao, pedidos[i])["numero"])

    # Nenhuma criação falha (antes: 409 na colisão do MAX + 1).
    assert not erros(res), erros(res)
    assert sorted(r.valor for r in res) == list(range(1, N + 1))


def test_oc_continua_do_maior_numero_existente(fabrica_sessao):
    pedidos = _pedidos(fabrica_sessao, 2)
    db = fabrica_sessao()
    try:
        # OC antiga (cancelada) gravada antes da sequência existir.
        db.add(OrdemCorte(numero=41, pedido_id=pedidos[0], status="CANCELADA", pedido_hash="x"))
        db.commit()
        assert svc.criar_ordem_corte(db, pedidos[1])["numero"] == 42
    finally:
        db.close()


def test_segunda_oc_do_mesmo_pedido_nao_consome_numero(fabrica_sessao):
    pedidos = _pedidos(fabrica_sessao, 2)
    db = fabrica_sessao()
    try:
        assert svc.criar_ordem_corte(db, pedidos[0])["numero"] == 1
        with pytest.raises(svc.ErroOC) as exc:
            svc.criar_ordem_corte(db, pedidos[0])
        assert exc.value.status == 409
        assert svc.criar_ordem_corte(db, pedidos[1])["numero"] == 2
    finally:
        db.close()


def test_encaixes_gravados_ao_mesmo_tempo_tem_numeros_unicos(fabrica_sessao):
    pedidos = _pedidos(fabrica_sessao, N)

    def fn(sessao, i):
        encaixes = [_encaixe(pedidos[i]) for _ in range(3)]
        nesting_service._gravar(sessao, encaixes)
        return [e.numero for e in encaixes]

    res = disputar(fabrica_sessao, N, fn)
    assert not erros(res), erros(res)
    numeros = sorted(n for r in res for n in r.valor)
    assert numeros == list(range(1, 3 * N + 1))
    # Os encaixes de uma mesma gravação ficam em sequência (um commit só).
    for r in res:
        assert r.valor == list(range(r.valor[0], r.valor[0] + 3))


def test_encaixe_continua_do_maior_inclusive_deletado(fabrica_sessao):
    (pedido,) = _pedidos(fabrica_sessao, 1)
    db = fabrica_sessao()
    try:
        antigo = _encaixe(pedido)
        antigo.numero, antigo.status = 7, "deletado"
        db.add(antigo)
        db.commit()
        novos = [_encaixe(pedido), _encaixe(pedido)]
        nesting_service._gravar(db, novos)
        assert [e.numero for e in novos] == [8, 9]
    finally:
        db.close()
