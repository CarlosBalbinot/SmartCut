"""Motor de encaixe v2 (services/nesting_v2) — M1-B.

Espelho dos pares sobre o eixo do fio, tabela por mesa (moldes) × grade do
enfesto, mochila do CP-SAT e uma geração pequena de ponta a ponta com o
spyrrow (peças retangulares e em L, limite de mesa, sem sobreposição).
"""

import pytest
from shapely.geometry import Polygon

from services.nesting_v2 import ErroEncaixe, Peca, gerar, preparar
from services.nesting_v2.geometria import eixo_do_fio, espelhar, grade_por_tamanho, por_molde
from services.nesting_v2.memoria import MedidorPico
from services.nesting_v2.planejador import area_bloco, blocos, mochila

# "L" assimétrico: o espelho dele não é nenhuma rotação dele
L = [[0, 0], [30, 0], [30, 10], [10, 10], [10, 60], [0, 60]]


def _rect(w, h):
    return [[0, 0], [w, 0], [w, h], [0, h]]


# ── Espelho ──────────────────────────────────────────────────────────────


def test_eixo_do_fio_pelas_rotacoes():
    assert eixo_do_fio((0.0, 180.0)) == "y"
    assert eixo_do_fio((90.0, 270.0)) == "x"
    assert eixo_do_fio((0.0, 90.0, 180.0, 270.0)) == "y"


def test_espelhar_sobre_o_fio_vertical_inverte_x():
    esp = espelhar(L, "y")
    assert esp[1] == [0, 0] and esp[0] == [30, 0]  # x → 30 − x
    assert Polygon(esp).area == pytest.approx(Polygon(L).area)
    assert not Polygon(esp).equals(Polygon(L))


def test_espelhar_sobre_o_fio_horizontal_inverte_y():
    esp = espelhar(L, "x")
    assert [p[0] for p in esp] == [p[0] for p in L]
    assert esp[0] == [0, 60]  # y → 60 − y


def test_par_segunda_copia_espelhada_e_par_sem_espelho_igual():
    par = preparar([Peca(id="m", poligono=L, quantidade=4, tipo_corte="par")])
    assert [u.espelhada for u in par] == [False, True, False, True]
    assert par[0].par == par[1].par != par[2].par == par[3].par
    assert Polygon(par[1].poligono).equals(Polygon(espelhar(par[0].poligono, "y")))

    igual = preparar([Peca(id="m", poligono=L, quantidade=2, tipo_corte="par_sem_espelho")])
    assert [u.espelhada for u in igual] == [False, False]
    assert igual[0].poligono == igual[1].poligono


def test_par_com_quantidade_impar_e_erro():
    with pytest.raises(ValueError):
        preparar([Peca(id="m", poligono=L, quantidade=3, tipo_corte="par")])


# ── Tabela por mesa × grade do enfesto ───────────────────────────────────


def test_por_molde_lista_moldes_e_grade_fica_no_enfesto():
    us = preparar(
        [
            Peca(id="frente-g", poligono=_rect(10, 10), quantidade=1, peca="FRENTE", tamanho="G"),
            Peca(id="costas-m", poligono=L, quantidade=2, tipo_corte="par", peca="COSTAS", tamanho="M"),
        ]
    )
    moldes = por_molde(us, camadas=3)
    assert [(m["peca"], m["tamanho"], m["por_camada"], m["espelhadas"], m["total"]) for m in moldes] == [
        ("FRENTE", "G", 1, 0, 3),
        ("COSTAS", "M", 2, 1, 6),
    ]
    grade = {g["tamanho"]: (g["pecas"], g["total"]) for g in grade_por_tamanho(us, camadas=3)}
    assert grade == {"G": (1, 3), "M": (2, 6)}


# ── Mochila (CP-SAT) ─────────────────────────────────────────────────────


def test_mochila_maior_area_que_cabe_e_par_inteiro():
    us = preparar(
        [
            Peca(id="a", poligono=_rect(10, 10), quantidade=1),  # 100
            Peca(id="b", poligono=_rect(10, 7), quantidade=2, tipo_corte="par_sem_espelho"),  # 2 × 70
            Peca(id="c", poligono=_rect(5, 10), quantidade=1),  # 50
        ]
    )
    bl = blocos(us)
    assert [round(area_bloco(b)) for b in bl] == [140, 100, 50]
    escolhido = mochila(bl, 195)
    assert round(sum(area_bloco(b) for b in escolhido)) == 190  # 140 + 50: o par não se separa
    assert mochila(bl, 10) == []


# ── Memória ──────────────────────────────────────────────────────────────


def test_medidor_de_pico():
    with MedidorPico(intervalo_s=0.01) as m:
        _ = bytearray(20 * 1024 * 1024)
    if m.pico_mb is not None:  # plataforma sem medição devolve None
        assert m.pico_mb >= m.inicio_mb > 0


# ── Ponta a ponta (spyrrow) ──────────────────────────────────────────────

RAPIDO = {"segundos_mesa": 1, "segundos_polimento": 0, "seed": 0}


def _sem_sobreposicao(mesa):
    polys = [Polygon(p.pontos) for p in mesa.posicoes]
    return all(polys[i].intersection(polys[j]).area < 0.5 for i in range(len(polys)) for j in range(i + 1, len(polys)))


def test_gerar_respeita_limite_pares_e_tabela_por_mesa():
    pecas = [
        Peca(id="grande", poligono=_rect(45, 90), quantidade=4, peca="FRENTE", tamanho="G"),
        Peca(id="l", poligono=L, quantidade=2, tipo_corte="par", peca="MANGA", tamanho="G"),
        Peca(id="cos", poligono=_rect(30, 15), quantidade=3, peca="CÓS", tamanho="G"),
    ]
    r = gerar(pecas, 100, 120, camadas=2, **RAPIDO)

    assert sum(len(m.unidades) for m in r.mesas) == 9
    for m in r.mesas:
        assert m.comprimento_cm <= 120 + 1e-3
        assert max(max(x for x, _ in p.pontos) for p in m.posicoes) <= 100 + 1e-3
        assert _sem_sobreposicao(m)
        pares = [u.par for u in m.unidades if u.par is not None]
        assert all(pares.count(p) == 2 for p in pares)  # par nunca dividido

    espelhadas = [pl for m in r.mesas for pl in m.pecas if pl["espelhada"]]
    assert len(espelhadas) == 1 and espelhadas[0]["id"] == "l"

    mapas = r.mapas_json(lote_id="x")
    assert all("pecas_por_tamanho" not in mp for mp in mapas)
    assert sum(linha["por_camada"] for mp in mapas for linha in mp["pecas_parte"]) == 9
    assert all(mp["total_partes"] == len(r.mesas) and mp["lote_id"] == "x" for mp in mapas)

    resumo = r.resumo_enfesto()
    assert resumo["pecas_por_tamanho"] == [{"grupo_nome": None, "tamanho": "G", "pecas": 9, "total": 18, "sobra": 0}]
    assert resumo["total_partes"] == len(r.mesas)
    assert r.chamadas_spyrrow > 0 and r.segundos > 0


def test_gerar_sem_limite_faz_uma_faixa():
    r = gerar([Peca(id="a", poligono=_rect(40, 50), quantidade=5)], 100, None, **RAPIDO)
    assert len(r.mesas) == 1 and len(r.mesas[0].unidades) == 5


def test_peca_maior_que_a_mesa_e_erro():
    with pytest.raises(ErroEncaixe):
        gerar([Peca(id="a", poligono=_rect(40, 200), quantidade=1)], 100, 150, **RAPIDO)
