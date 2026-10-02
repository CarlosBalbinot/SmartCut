"""Débito e crédito do lote sob disputa (F0, passo 2b).

Antes, o peso novo era calculado em Python a partir do valor lido no início
da ação (`peso lido − consumo`) e gravado por cima: várias OCs diferentes
concluídas ao mesmo tempo no mesmo lote liam o mesmo saldo e cada uma
gravava o seu resultado — só uma baixa ficava. Agora o UPDATE calcula no
banco (`peso = peso − :kg`), então as baixas se somam.
"""

import uuid
from decimal import Decimal

from sqlalchemy import func, select

from models.tecido import ConsumoLote, LoteTecido
from services import lote_service
from services import ordem_corte_service as svc
from tests.concorrencia import cenario
from tests.concorrencia.disputa import disputar
from tests.test_ordem_corte_producao import PESO_LOTE

N = 6


def _lote(fabrica, lote_id) -> tuple[Decimal, str]:
    db = fabrica()
    try:
        lote = db.get(LoteTecido, lote_id)
        return Decimal(str(lote.peso_disponivel_kg)), lote.status
    finally:
        db.close()


def _consumos(fabrica, lote_id) -> int:
    db = fabrica()
    try:
        return db.execute(
            select(func.count()).where(ConsumoLote.lote_id == lote_id, ConsumoLote.tipo == "CONSUMO")
        ).scalar_one()
    finally:
        db.close()


def _kg(i: int) -> Decimal:
    """Consumos diferentes por OC, com 3 casas (1.111, 2.222, ...)."""
    return Decimal("1.111") * (i + 1)


def test_ocs_diferentes_concluidas_juntas_somam_as_baixas(fabrica_sessao):
    ids, lote_id = cenario.ocs(fabrica_sessao, N, "EM_CORTE")

    res = disputar(
        fabrica_sessao,
        N,
        lambda sessao, i: svc.concluir(sessao, ids[i], "ANA", [{"lote_id": lote_id, "kg_real": _kg(i)}]),
    )

    assert all(r.ok for r in res), [repr(r.erro) for r in res if not r.ok]
    peso, status = _lote(fabrica_sessao, lote_id)
    assert peso == Decimal(str(PESO_LOTE)) - sum(_kg(i) for i in range(N))  # 50 − 23.331 = 26.669
    assert status == "aberto"
    assert _consumos(fabrica_sessao, lote_id) == N


def test_ocs_reabertas_juntas_devolvem_tudo(fabrica_sessao):
    ids, lote_id = cenario.ocs(fabrica_sessao, N, "CONCLUIDA")
    assert _lote(fabrica_sessao, lote_id)[0] < Decimal(str(PESO_LOTE))

    res = disputar(fabrica_sessao, N, lambda sessao, i: svc.reabrir(sessao, ids[i], "ANA"))

    assert all(r.ok for r in res), [repr(r.erro) for r in res if not r.ok]
    assert _lote(fabrica_sessao, lote_id) == (Decimal(str(PESO_LOTE)), "aberto")


def test_baixas_juntas_maiores_que_o_saldo_param_no_zero(fabrica_sessao):
    ids, lote_id = cenario.ocs(fabrica_sessao, 4, "EM_CORTE")

    # 4 × 20 kg = 80 kg num lote de 50 kg.
    res = disputar(
        fabrica_sessao,
        4,
        lambda sessao, i: svc.concluir(sessao, ids[i], "ANA", [{"lote_id": lote_id, "kg_real": 20}]),
    )

    assert all(r.ok for r in res), [repr(r.erro) for r in res if not r.ok]
    assert _lote(fabrica_sessao, lote_id) == (Decimal("0"), "esgotado")


def test_debito_maior_que_o_saldo_para_no_zero_e_esgota(fabrica_sessao):
    (oc_id,), lote_id = cenario.ocs(fabrica_sessao, 1, "EM_CORTE")

    db = fabrica_sessao()
    try:
        svc.concluir(db, oc_id, "ANA", [{"lote_id": lote_id, "kg_real": PESO_LOTE + 30}])
    finally:
        db.close()

    assert _lote(fabrica_sessao, lote_id) == (Decimal("0"), "esgotado")


def test_credito_reativa_lote_esgotado_e_arquivado_continua_arquivado(fabrica_sessao):
    (_,), lote_id = cenario.ocs(fabrica_sessao, 1, "RASCUNHO")

    db = fabrica_sessao()
    try:
        assert lote_service.debitar(db, lote_id, PESO_LOTE)
        db.commit()
        assert _lote(fabrica_sessao, lote_id) == (Decimal("0"), "esgotado")

        assert lote_service.creditar(db, lote_id, Decimal("1.5"))
        db.commit()
        assert _lote(fabrica_sessao, lote_id) == (Decimal("1.5"), "aberto")

        db.get(LoteTecido, lote_id).status = "arquivado"
        db.commit()
        assert lote_service.creditar(db, lote_id, 1)
        db.commit()
        assert _lote(fabrica_sessao, lote_id) == (Decimal("2.5"), "arquivado")
    finally:
        db.close()


def test_consumir_usa_o_mesmo_caminho(fabrica_sessao):
    (_,), lote_id = cenario.ocs(fabrica_sessao, 1, "RASCUNHO")

    db = fabrica_sessao()
    try:
        # O objeto carregado antes do débito não fica com o peso velho.
        lote = db.get(LoteTecido, lote_id)
        out = lote_service.consumir(db, lote_id, 0.0005)  # arredonda para 0.001
        assert out.peso_disponivel_kg == float(Decimal(str(PESO_LOTE)) - Decimal("0.001"))
        assert out.status == "aberto"
        assert Decimal(str(lote.peso_disponivel_kg)) == Decimal("49.999")
        assert lote_service.consumir(db, uuid.uuid4(), 1) is None
    finally:
        db.close()
