"""Sequências atômicas (F0, passo 1a): services/sequencia_service.py.

A disputa entre sessões de verdade fica em tests/concorrencia/test_sequencias.py.
"""

from models.sequencia import Sequencia
from services import sequencia_service as seq


def test_primeiro_uso_comeca_em_1(db_session):
    assert seq.proximo(db_session, "oc") == 1
    assert seq.proximo(db_session, "oc") == 2
    assert seq.atual(db_session, "oc") == 2


def test_primeiro_uso_continua_do_maior_ja_usado(db_session):
    chamadas = []

    def inicial(db):
        chamadas.append(1)
        return 41

    assert seq.proximo(db_session, "encaixe", inicial) == 42
    assert seq.proximo(db_session, "encaixe", inicial) == 43
    # `inicial` só roda na criação da sequência.
    assert len(chamadas) == 1


def test_sequencias_sao_independentes(db_session):
    assert seq.proximo(db_session, "produto:a") == 1
    assert seq.proximo(db_session, "produto:a") == 2
    assert seq.proximo(db_session, "produto:b") == 1


def test_nao_faz_commit_e_rollback_devolve_o_numero(db_session):
    seq.proximo(db_session, "oc")
    db_session.commit()
    assert seq.proximo(db_session, "oc") == 2
    db_session.rollback()
    # O número 2 não foi consumido: a transação que o pegou foi desfeita.
    assert seq.proximo(db_session, "oc") == 2


def test_atual_nao_consome_nem_cria(db_session):
    assert seq.atual(db_session, "oc") == 0
    assert seq.atual(db_session, "oc", lambda db: 7) == 7
    assert db_session.get(Sequencia, "oc") is None
    assert seq.proximo(db_session, "oc", lambda db: 7) == 8


def test_garantir_minimo_sobe_mas_nunca_desce(db_session):
    seq.proximo(db_session, "grupo_produto")  # 1
    seq.garantir_minimo(db_session, "grupo_produto", 10)
    assert seq.proximo(db_session, "grupo_produto") == 11
    seq.garantir_minimo(db_session, "grupo_produto", 3)
    assert seq.proximo(db_session, "grupo_produto") == 12


def test_garantir_minimo_em_sequencia_nova(db_session):
    # Sem a linha: cria no maior entre o já usado (inicial) e o informado.
    seq.garantir_minimo(db_session, "sku:CAM", 5, lambda db: 9)
    assert seq.proximo(db_session, "sku:CAM") == 10
    seq.garantir_minimo(db_session, "sku:BLU", 5, lambda db: 2)
    assert seq.proximo(db_session, "sku:BLU") == 6
