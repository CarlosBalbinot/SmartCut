"""Transições da OC sob disputa (F0, passo 2a).

Antes, cada ação conferia o status em Python e gravava sem condição: duas
ações ao mesmo tempo passavam na conferência e as duas gravavam (baixa dupla
do lote, OC cancelada que volta a ENVIADA). Agora o status muda com
UPDATE ... WHERE status IN (...) antes de mexer no estoque, e quem perde sai
com 409 OC_STATUS_MUDOU.
"""

import pytest
from sqlalchemy import func, select

from models.ordem_corte import OrdemCorte
from models.tecido import ConsumoLote, LoteTecido
from services import ordem_corte_service as svc
from tests.concorrencia import cenario
from tests.concorrencia.disputa import disputar
from tests.test_ordem_corte_producao import PESO_LOTE, PLANEJADO


def _so_409(res) -> None:
    """Quem falhou, falhou com 409 de regra da OC — nunca 500 nem outro erro."""
    for r in res:
        if not r.ok:
            assert isinstance(r.erro, svc.ErroOC), repr(r.erro)
            assert r.erro.status == 409, r.erro.mensagem


def _estado(fabrica, oc_id, lote_id) -> tuple[str, float, int, int]:
    """(status da OC, peso do lote, nº de CONSUMO, nº de ESTORNO)."""
    db = fabrica()
    try:
        status = db.execute(select(OrdemCorte.status).where(OrdemCorte.id == oc_id)).scalar_one()
        peso = float(db.get(LoteTecido, lote_id).peso_disponivel_kg)

        def contar(tipo):
            return db.execute(
                select(func.count()).where(ConsumoLote.ordem_corte_id == oc_id, ConsumoLote.tipo == tipo)
            ).scalar_one()

        return status, peso, contar("CONSUMO"), contar("ESTORNO")
    finally:
        db.close()


def test_concluir_x_concluir_debita_uma_vez(fabrica_sessao):
    (oc_id,), lote_id = cenario.ocs(fabrica_sessao, 1, "EM_CORTE")

    res = disputar(fabrica_sessao, 4, lambda sessao, i: svc.concluir(sessao, oc_id, f"CORTADOR {i}", []))

    _so_409(res)
    assert sum(r.ok for r in res) == 1
    status, peso, consumos, estornos = _estado(fabrica_sessao, oc_id, lote_id)
    assert (status, consumos, estornos) == ("CONCLUIDA", 1, 0)
    assert peso == PESO_LOTE - PLANEJADO  # uma baixa só
    # Quem perdeu a disputa recebe o código e o status atual.
    for r in res:
        if not r.ok and r.erro.codigo == svc.OC_STATUS_MUDOU:
            assert r.erro.params == {"status_atual": "CONCLUIDA"}


def test_concluir_x_reabrir_mantem_estoque_coerente(fabrica_sessao):
    # Concluída; metade das sessões reabre e metade conclui, todas juntas.
    # Qualquer ordem que o banco escolha, o fim tem de ser coerente: o lote
    # perdeu exatamente o consumo que continua valendo, e o status bate.
    (oc_id,), lote_id = cenario.ocs(fabrica_sessao, 1, "CONCLUIDA")

    def fn(sessao, i):
        if i % 2:
            return svc.concluir(sessao, oc_id, "ANA", [])
        return svc.reabrir(sessao, oc_id, "SUPERVISOR")

    res = disputar(fabrica_sessao, 6, fn)

    _so_409(res)
    status, peso, consumos, estornos = _estado(fabrica_sessao, oc_id, lote_id)
    vivos = consumos - estornos
    assert vivos in (0, 1)
    assert status == ("CONCLUIDA" if vivos else "EM_CORTE")
    assert peso == PESO_LOTE - PLANEJADO * vivos


def test_enviar_x_cancelar_nao_ressuscita_oc_cancelada(fabrica_sessao):
    # 10 OCs em RASCUNHO; para cada uma, uma sessão envia e outra cancela.
    # Se o cancelamento passou, a OC termina CANCELADA (enviar antes e
    # cancelar depois também é válido); nunca ENVIADA depois de cancelada.
    oc_ids, _ = cenario.ocs(fabrica_sessao, 10, "RASCUNHO")

    def fn(sessao, i):
        oc_id = oc_ids[i // 2]
        if i % 2:
            return svc.cancelar(sessao, oc_id)
        return svc.enviar_a_producao(sessao, oc_id)

    res = disputar(fabrica_sessao, 20, fn)

    _so_409(res)
    db = fabrica_sessao()
    try:
        for n, oc_id in enumerate(oc_ids):
            enviou, cancelou = res[2 * n].ok, res[2 * n + 1].ok
            status = db.execute(select(OrdemCorte.status).where(OrdemCorte.id == oc_id)).scalar_one()
            assert enviou or cancelou
            if cancelou:
                assert status == "CANCELADA", f"OC {n}: cancelada, mas terminou {status}"
            else:
                assert status == "ENVIADA"
    finally:
        db.close()


def test_409_tem_codigo_e_status_atual(fabrica_sessao):
    # Sessão A carregou a OC em EM_CORTE; a B concluiu antes de A gravar.
    (oc_id,), _ = cenario.ocs(fabrica_sessao, 1, "EM_CORTE")
    a, b = fabrica_sessao(), fabrica_sessao()
    try:
        oc_em_a = a.get(OrdemCorte, oc_id)
        svc.concluir(b, oc_id, "ANA", [])

        with pytest.raises(svc.ErroOC) as exc:
            svc._transicionar(a, oc_em_a, ("EM_CORTE",), "CONCLUIDA")
        erro = exc.value
        assert (erro.status, erro.codigo, erro.params) == (409, "OC_STATUS_MUDOU", {"status_atual": "CONCLUIDA"})
        assert "agora está CONCLUIDA" in erro.mensagem
    finally:
        a.close()
        b.close()
