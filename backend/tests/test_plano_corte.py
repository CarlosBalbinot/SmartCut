"""PC1 · Passo 2 — plano de corte multicor (services/planejamento/plano_corte.py)
e o estimador. Tudo puro: nenhum banco, nenhum motor.

Grades de verdade: a OC-0004 (três cores com a mesma grade, 108 peças cada) e
o pedido da Dany (várias cores com grades pequenas e NÃO proporcionais). A
área dos conjuntos é a da LEGGING FLARE da OC-0004.
"""

import pytest

from services.planejamento import estimador
from services.planejamento.plano_corte import (
    CorGrade,
    _enfestos,
    agrupar_cores,
    planejar_corte,
    plano_por_cor,
)

AREA = {"P": 10341, "M": 10994, "G": 11662, "GG": 12364}  # cm² por conjunto (par = 2 peças)
GRADE_OC4 = {"P": 18, "M": 30, "G": 40, "GG": 20}
LIMITE = 150


def _plano(cores, **kw):
    return planejar_corte(cores, AREA, limite_mesa_cm=LIMITE, **kw)


def _confere(plano, cores):
    """Nenhuma cor falta, sobra bate e o teto vale em todo enfesto."""
    cortado = plano.cortado()
    for c in cores:
        for t, q in c.grade.items():
            assert cortado[c.cor].get(t, 0) >= q, (c.cor, t)
            assert cortado[c.cor].get(t, 0) - q == plano.sobra_por_cor.get(c.cor, {}).get(t, 0)
    for r in plano.riscos:
        assert sum(sum(e.values()) for e in r.enfestos) == r.camadas
        for e in r.enfestos:
            assert sum(e.values()) <= plano.teto_camadas


# ── Estimador ───────────────────────────────────────────────────────────────


def test_estimador_reproduz_os_riscos_da_oc_0004():
    # comprimento e mesas reais do motor (mesa de 150 cm, MAXXI 150 cm)
    reais = [
        ({"P": 1, "M": 2, "G": 2, "GG": 1}, 583, 5),
        ({"P": 1, "G": 3, "GG": 1}, 503, 5),
        ({"G": 1, "GG": 2}, 331, 3),
    ]
    for conjuntos, comp_real, mesas_real in reais:
        comp, mesas = estimador.estimar(conjuntos, AREA, 150, 150)
        assert mesas == mesas_real
        assert comp == pytest.approx(comp_real, rel=0.06)


def test_estimador_risco_longo_paga_ponta_por_mesa():
    um, m1 = estimador.estimar({"M": 1}, AREA, 150, 150)
    dez, m10 = estimador.estimar({"M": 10}, AREA, 150, 150)
    assert m10 > m1 == 1
    assert dez == pytest.approx(10 * (um - estimador.PERDA_MESA_CM) + m10 * estimador.PERDA_MESA_CM)


# ── Grupos de cores ─────────────────────────────────────────────────────────


def test_empilha_mesmo_tecido_com_ate_5_cm_de_diferenca():
    preto = CorGrade("PRETO", GRADE_OC4, "MAXXI", 150, 15)
    marrom = CorGrade("MARROM", GRADE_OC4, "MAXXI", 146, 15)
    verde = CorGrade("VERDE MILITAR", GRADE_OC4, "CANELADO WISH", 130, 10)
    grupos = agrupar_cores([preto, marrom, verde])
    assert [[c.cor for c in g] for g in grupos] == [["PRETO", "MARROM"], ["VERDE MILITAR"]]

    # 144..150 = 6 cm: separa
    bruma = CorGrade("BRUMA", GRADE_OC4, "MAXXI", 144, 15)
    grupos = agrupar_cores([preto, bruma])
    assert sorted([c.cor for c in g] for g in grupos) == [["BRUMA"], ["PRETO"]]


# ── OC-0004 ─────────────────────────────────────────────────────────────────


def test_oc_0004_preto_menos_mesas_sem_gastar_mais():
    preto = [CorGrade("PRETO", GRADE_OC4, "MAXXI", 150, 15)]
    hoje = plano_por_cor(preto, AREA, limite_mesa_cm=LIMITE)
    plano = _plano(preto)
    _confere(plano, preto)
    assert (hoje.desenhos, hoje.mesas) == (3, 13)
    assert plano.sobra_total == 0
    assert plano.mesas == 8  # 13 → 8
    assert plano.metros <= hoje.metros * 1.02
    assert plano.otimo


def test_oc_0004_verde_nunca_aceita_sobra_para_economizar_desenho():
    # 1 desenho só (P2 M3 G4 GG2 × 10) daria 2 P a mais e +1,7% de tecido
    # com as MESMAS 11 mesas — não vale.
    verde = [CorGrade("VERDE MILITAR", GRADE_OC4, "CANELADO WISH", 130, 10)]
    hoje = plano_por_cor(verde, AREA, limite_mesa_cm=LIMITE)
    plano = _plano(verde)
    _confere(plano, verde)
    assert plano.sobra_total == 0
    assert (plano.desenhos, plano.mesas) == (hoje.desenhos, hoje.mesas) == (2, 11)


def test_oc_0004_preto_e_marrom_empilham_so_onde_compensa():
    cores = [CorGrade("PRETO", GRADE_OC4, "MAXXI", 150, 15), CorGrade("MARROM", GRADE_OC4, "MAXXI", 146, 15)]
    plano = _plano(cores)
    _confere(plano, cores)
    assert plano.sobra_total == 0
    hoje = plano_por_cor(cores, AREA, limite_mesa_cm=LIMITE)
    assert plano.mesas < hoje.mesas and plano.desenhos < hoje.desenhos
    assert plano.metros <= plano.metros_minimo * 1.02
    # o risco grande do PRETO fica na largura dele (150); os pequenos, com as
    # duas cores, na menor (146)
    grande_preto = next(r for r in plano.riscos if r.camadas_por_cor == {"PRETO": 15})
    assert grande_preto.largura_cm == 150
    empilhados = [r for r in plano.riscos if set(r.camadas_por_cor) == {"PRETO", "MARROM"}]
    assert empilhados and all(r.largura_cm == 146 for r in empilhados)
    # cor nunca vai num risco mais largo que ela
    assert all(r.largura_cm <= 146 for r in plano.riscos if "MARROM" in r.camadas_por_cor)


def test_tolerancia_zero_e_o_menor_consumo():
    verde = [CorGrade("VERDE MILITAR", GRADE_OC4, "CANELADO WISH", 130, 10)]
    exato = _plano(verde, tolerancia_pct=0.0)
    assert exato.metros == pytest.approx(exato.metros_minimo, abs=0.01)
    assert exato.sobra_total == 0 and exato.desenhos == 2
    assert _plano(verde).mesas <= exato.mesas


# ── Pedido da Dany (grades não proporcionais) ───────────────────────────────


def _dany(**grades):
    return [CorGrade(cor.replace("_", " "), g, "MAXXI", 150, 15) for cor, g in grades.items()]


COS_INFINITO = _dany(
    PRETO={"M": 2, "G": 2},
    AZUL_MARINHO={"M": 1, "G": 1},
    BRUMA={"M": 2},
    ELEGANCE={"P": 1, "M": 1},
    OFFWHITE={"P": 1, "M": 1},
    CEREJA={"P": 1, "M": 2, "G": 1},
)
FLARE_EMPINA = _dany(
    PRETO={"M": 2, "G": 2},
    MARROM={"M": 2, "G": 1},
    BRUMA={"P": 1, "M": 2},
    ELEGANCE={"M": 2},
    VALENTINO={"P": 1, "M": 2, "G": 1},
    OFFWHITE={"P": 1, "M": 2},
    AZUL_SKY={"GG": 1},
)


def test_dany_cos_infinito_empilha_as_cores_por_tamanho():
    plano = _plano(COS_INFINITO)
    _confere(plano, COS_INFINITO)
    hoje = plano_por_cor(COS_INFINITO, AREA, limite_mesa_cm=LIMITE)
    assert (hoje.desenhos, hoje.mesas) == (6, 13)
    assert (plano.desenhos, plano.mesas, plano.sobra_total) == (3, 3, 0)
    assert plano.metros <= hoje.metros + 0.01
    m1 = next(r for r in plano.riscos if r.conjuntos == {"M": 1})
    assert m1.camadas_por_cor == {"PRETO": 2, "AZUL MARINHO": 1, "BRUMA": 2, "ELEGANCE": 1, "OFFWHITE": 1, "CEREJA": 2}


def test_dany_flare_nenhuma_cor_falta_nem_a_de_uma_peca():
    plano = _plano(FLARE_EMPINA)
    _confere(plano, FLARE_EMPINA)
    assert plano.sobra_total == 0
    assert plano.cortado()["AZUL SKY"] == {"GG": 1}
    assert plano.mesas <= 4


def test_enfesto_duplo_com_par_usa_camadas_pares_por_cor():
    plano = _plano(COS_INFINITO, camadas_pares=True)
    _confere(plano, COS_INFINITO)
    assert plano.teto_camadas == 14  # 15 → par abaixo
    for r in plano.riscos:
        assert all(n % 2 == 0 for n in r.camadas_por_cor.values())
        assert all(n % 2 == 0 for e in r.enfestos for n in e.values())
    # quem pediu 1 peça de um tamanho leva 2: a sobra é informada
    assert plano.sobra_por_cor["AZUL MARINHO"] == {"M": 1, "G": 1}
    # a sobra é a mínima que as camadas pares obrigam: o plano por cor de hoje
    # (também em camadas pares) não sobra menos
    hoje = plano_por_cor(COS_INFINITO, AREA, limite_mesa_cm=LIMITE, camadas_pares=True)
    assert plano.sobra_total <= hoje.sobra_total
    assert "inevitável" in plano.motivo


def test_teto_e_a_soma_das_cores_no_enfesto():
    cores = _dany(PRETO={"M": 10}, BRUMA={"M": 10})
    plano = _plano([CorGrade(c.cor, c.grade, "MAXXI", 150, 12) for c in cores])
    _confere(plano, cores)
    # 20 camadas de M1 não cabem num enfesto de 12: são dois, somando as cores
    assert plano.teto_camadas == 12
    assert sum(len(r.enfestos) for r in plano.riscos) >= 2


def test_mesmo_pedido_mesmo_plano():
    assert _plano(FLARE_EMPINA).json() == _plano(FLARE_EMPINA).json()


# ── Pedaços ─────────────────────────────────────────────────────────────────


def test_enfestos_divide_so_quando_nao_cabe_e_mantem_par():
    assert _enfestos({"PRETO": 8, "BRUMA": 6}, 1, 14) == [{"PRETO": 8, "BRUMA": 6}]
    assert _enfestos({"PRETO": 10, "BRUMA": 8}, 2, 14) == [{"PRETO": 10, "BRUMA": 4}, {"BRUMA": 4}]


def test_erros_de_entrada():
    with pytest.raises(ValueError, match="sem área"):
        planejar_corte([CorGrade("PRETO", {"XG": 1}, "MAXXI", 150, 15)], AREA, limite_mesa_cm=LIMITE)
    with pytest.raises(ValueError, match="pelo menos 2 camadas"):
        planejar_corte([CorGrade("PRETO", {"M": 1}, "MAXXI", 150, 1)], AREA, limite_mesa_cm=LIMITE, camadas_pares=True)
