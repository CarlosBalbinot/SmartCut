"""Decisão automática do enfesto (F2) — nesting_v2/decisor.py, camadas pares
do plano_enfesto e a decisão de ponta a ponta no nesting_service.

Os testes do decisor são puros; os de ponta a ponta rodam o motor de verdade
(spyrrow, perfil RÁPIDO) com peças pequenas, sem gravar nada.
"""

import time
import uuid
from datetime import date

import pytest

from models.molde import Molde
from models.tecido import CorTecido, LoteTecido, ModeloTecido
from services import nesting_service as svc
from services.nesting_v2 import decisor
from services.nesting_v2.decisor import FACE_A_FACE, MESMA_FACE, Analise, Candidato
from services.plano_enfesto import camadas_par, planejar

RETANGULO = [[0, 0], [40, 0], [40, 60], [0, 60]]
# "L" assimétrico: o espelho dele não é nenhuma rotação dele
L = [[0, 0], [30, 0], [30, 10], [10, 10], [10, 60], [0, 60]]


# ── Classificação das peças ───────────────────────────────────────────────


def test_classificar_pecas():
    assert decisor.classificar(RETANGULO, (0, 180), "simples") == decisor.UNICO_SIMETRICO
    assert decisor.classificar(L, (0, 180), "simples") == decisor.UNICO_ASSIMETRICO
    assert decisor.classificar(L, (0, 180), "par") == decisor.PAR
    assert decisor.classificar(L, (0, 180), "par_sem_espelho") == decisor.PAR


def test_simetria_com_tolerancia():
    # Retângulo com um canto 0,2 cm fora: desvio médio bem abaixo de 0,3 cm.
    quase = [[0, 0], [40, 0], [40, 60], [0.2, 60]]
    assert decisor.desvio_simetria_cm(quase, (0, 180)) < decisor.TOLERANCIA_SIMETRIA_CM
    assert decisor.classificar(quase, (0, 180), "simples") == decisor.UNICO_SIMETRICO
    assert decisor.desvio_simetria_cm(L, (0, 180)) > 1.0


# ── Validade do face a face ───────────────────────────────────────────────


def _pecas(**tipos):
    formas = {"ret": RETANGULO, "l": L}
    return {
        nome: decisor.PecaAnalise(nome=nome.upper(), poligono=formas[forma], rotacoes=(0.0, 180.0), tipo_corte=tipo)
        for nome, (forma, tipo) in tipos.items()
    }


def test_face_a_face_valida_com_par_em_tecido_liso():
    a = decisor.analisar(
        _pecas(frente=("ret", "simples"), manga=("l", "par")),
        tem_direcao=False,
        camadas_naturais=[4],
        max_camadas=15,
    )
    assert a.face_a_face_valida and a.tem_par and a.dupla


def test_face_a_face_invalida_com_tecido_com_direcao():
    a = decisor.analisar(_pecas(manga=("l", "par")), tem_direcao=True, camadas_naturais=[4], max_camadas=15)
    assert not a.face_a_face_valida
    assert "direção" in a.motivo_invalida


def test_face_a_face_invalida_com_peca_unica_assimetrica():
    a = decisor.analisar(_pecas(bolso=("l", "simples")), tem_direcao=False, camadas_naturais=[4], max_camadas=15)
    assert not a.face_a_face_valida
    assert "assimétrica" in a.motivo_invalida and "BOLSO" in a.motivo_invalida


def test_uma_camada_e_sempre_face_unica():
    a = decisor.analisar(_pecas(manga=("l", "par")), tem_direcao=False, camadas_naturais=[1], max_camadas=15)
    assert not a.face_a_face_valida
    assert "1 camada" in a.motivo_invalida
    assert [c.tipo for c in decisor.candidatos(a)] == [MESMA_FACE, MESMA_FACE]


def test_candidatos_padrao_seguro_primeiro_e_escolha_manual():
    a = decisor.analisar(_pecas(manga=("l", "par")), tem_direcao=False, camadas_naturais=[4], max_camadas=15)
    lista = decisor.candidatos(a)
    assert [(c.tipo, c.modo) for c in lista][0] == (MESMA_FACE, "SEM_SOBRA")
    assert len(lista) == 4
    assert [(c.tipo, c.modo) for c in decisor.candidatos(a, FACE_A_FACE, "SEM_SOBRA")] == [(FACE_A_FACE, "SEM_SOBRA")]
    # face a face pedida à mão num lote inválido volta para face única
    inval = decisor.analisar(_pecas(manga=("l", "par")), tem_direcao=True, camadas_naturais=[4], max_camadas=15)
    assert [c.tipo for c in decisor.candidatos(inval, FACE_A_FACE, "SEM_SOBRA")] == [MESMA_FACE]


# ── Escolha ───────────────────────────────────────────────────────────────


def _analise(tem_par=False, camadas=4, valida=True, pares=None):
    return Analise(
        classes={},
        tem_par=tem_par,
        assimetricas=[],
        tem_direcao=False,
        camadas_naturais=camadas,
        camadas_naturais_pares=(camadas % 2 == 0) if pares is None else pares,
        max_camadas=15,
        face_a_face_valida=valida,
    )


def _c(tipo, modo, metros, mesas=2, camadas=4, sobra=0):
    return Candidato(tipo=tipo, modo=modo, metros=metros, mesas=mesas, camadas=camadas, sobra=sobra)


def test_menor_consumo_vence():
    lista = [_c(MESMA_FACE, "SEM_SOBRA", 10.0), _c(FACE_A_FACE, "SEM_SOBRA", 10.5)]
    vencedor, motivo, regra = decisor.escolher(lista, _analise(tem_par=True))
    assert vencedor.tipo == MESMA_FACE and regra == "MENOR_CONSUMO"
    assert "menor consumo" in motivo


def test_empate_produto_dupla_prefere_face_a_face():
    lista = [_c(MESMA_FACE, "SEM_SOBRA", 10.0), _c(FACE_A_FACE, "SEM_SOBRA", 10.05)]
    vencedor, motivo, regra = decisor.escolher(lista, _analise(tem_par=True, camadas=2))
    assert vencedor.tipo == FACE_A_FACE and regra == "PRODUTO_DUPLA"
    assert "empate técnico" in motivo and "dupla" in motivo


def test_empate_com_2_ou_3_camadas_prefere_face_unica():
    lista = [_c(MESMA_FACE, "SEM_SOBRA", 10.05), _c(FACE_A_FACE, "SEM_SOBRA", 10.0)]
    vencedor, _, regra = decisor.escolher(lista, _analise(tem_par=False, camadas=3, pares=False))
    assert vencedor.tipo == MESMA_FACE and regra == "POUCAS_CAMADAS"


def test_empate_sem_regra_especial_prefere_face_a_face():
    lista = [_c(MESMA_FACE, "SEM_SOBRA", 10.0), _c(FACE_A_FACE, "SEM_SOBRA", 10.02)]
    vencedor, _, regra = decisor.escolher(lista, _analise(tem_par=False, camadas=5, pares=False))
    assert vencedor.tipo == FACE_A_FACE and regra == "MAIS_RAPIDO"


def test_sobra_so_vence_com_menor_consumo_fora_do_empate():
    empate = [_c(MESMA_FACE, "SEM_SOBRA", 10.05), _c(MESMA_FACE, "MENOS_ENFESTOS", 10.0, sobra=2)]
    assert decisor.escolher(empate, _analise())[0].sobra == 0
    fora = [_c(MESMA_FACE, "SEM_SOBRA", 11.0), _c(MESMA_FACE, "MENOS_ENFESTOS", 10.0, sobra=2)]
    assert decisor.escolher(fora, _analise())[0].sobra == 2


def test_empate_desfaz_por_menos_mesas_e_camadas():
    lista = [
        _c(MESMA_FACE, "SEM_SOBRA", 10.0, mesas=3),
        _c(MESMA_FACE, "MENOS_ENFESTOS", 10.02, mesas=2),
    ]
    assert decisor.escolher(lista, _analise(valida=False))[0].modo == "MENOS_ENFESTOS"


# ── Camadas pares (face a face com peça em par) ───────────────────────────


def test_camadas_par():
    assert camadas_par(4, 15) == 4
    assert camadas_par(3, 15) == 4
    assert camadas_par(15, 15) == 14
    assert camadas_par(1, 1) == 1


def test_plano_camadas_pares_registra_sobra():
    plano = planejar({"P": 1, "M": 2, "G": 3}, 15, "SEM_SOBRA", camadas_pares=True)
    assert all(e["camadas"] % 2 == 0 for e in plano["enfestos"])
    assert plano["sobra_total"] == 2
    assert all(plano["pecas_por_tamanho"][k] >= q for k, q in {"P": 1, "M": 2, "G": 3}.items())
    natural = planejar({"M": 4, "G": 2}, 15, "SEM_SOBRA", camadas_pares=True)
    assert natural["sobra_total"] == 0


# ── Ponta a ponta (motor de verdade, sem gravar) ─────────────────────────


def _lote(db, tem_direcao=False, max_camadas=15) -> LoteTecido:
    modelo = ModeloTecido(nome="LISO", tipo="Malha", max_camadas=max_camadas, tem_direcao=tem_direcao)
    db.add(modelo)
    db.commit()
    cor = CorTecido(
        modelo_id=modelo.id, nome_cor="PRETO", largura_util_cm=150.0, gramatura_g_m2=200.0, encolhimento_pct=0.0
    )
    db.add(cor)
    db.commit()
    lote = LoteTecido(
        cor_id=cor.id,
        codigo_lote=f"L{uuid.uuid4().hex[:6]}",
        peso_inicial_kg=50.0,
        peso_disponivel_kg=50.0,
        valor_kg=30.0,
        data_compra=date(2026, 1, 1),
    )
    db.add(lote)
    db.commit()
    db.refresh(lote)
    return lote


def _molde(db, peca, pontos, tipo_corte) -> Molde:
    m = Molde(
        nome=f"{peca} M",
        peca=peca,
        tamanho="M",
        sentido_fio="vertical",
        tipo_corte=tipo_corte,
        rotacao_base=0,
        geometria_json={"type": "Polygon", "coordinates": [pontos]},
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _decidir(db, lote, moldes, qtd=4):
    grupos = svc._agrupar_por_lote([(lote, m, qtd) for m in moldes])
    encaixes, _, planos, decisoes = svc._montar_todos(None, grupos, "AUTOMATICO", None, None, 150, "RAPIDO", None)
    return encaixes, planos, decisoes[str(lote.id)]


def test_ponta_a_ponta_par_em_tecido_liso_avalia_face_a_face(db_session):
    lote = _lote(db_session)
    moldes = [_molde(db_session, "FRENTE", RETANGULO, "simples"), _molde(db_session, "MANGA", L, "par")]
    encaixes, _, d = _decidir(db_session, lote, moldes)
    assert d.face_a_face_valida
    avaliados = {(c.tipo, c.modo) for c in d.candidatos if c.avaliado and c.erro is None}
    assert (FACE_A_FACE, "SEM_SOBRA") in avaliados and (MESMA_FACE, "SEM_SOBRA") in avaliados
    assert d.regra in ("MENOR_CONSUMO", "PRODUTO_DUPLA")
    # a contagem de peças cortadas é a mesma nos dois tipos: 4 frentes, 8 mangas
    total = {}
    for e in encaixes:
        for linha in e.mapa_json["pecas_parte"]:
            total[linha["peca"]] = total.get(linha["peca"], 0) + linha["total"]
    assert total == {"FRENTE": 4, "MANGA": 8}
    esperado_espelho = d.tipo == MESMA_FACE
    assert any(pl["espelhada"] for e in encaixes for pl in e.mapa_json["placements"]) == esperado_espelho
    assert all(e.mapa_json["tipo_enfesto"] == d.tipo for e in encaixes)
    assert encaixes[0].mapa_json["decisao_enfesto"]["tipo_enfesto"] == d.tipo


def test_ponta_a_ponta_tecido_com_direcao_e_face_unica(db_session):
    lote = _lote(db_session, tem_direcao=True)
    moldes = [_molde(db_session, "FRENTE", RETANGULO, "simples"), _molde(db_session, "MANGA", L, "par")]
    _, _, d = _decidir(db_session, lote, moldes)
    assert d.tipo == MESMA_FACE
    assert all(c.tipo == MESMA_FACE for c in d.candidatos)
    assert "direção" in d.motivo


def test_ponta_a_ponta_peca_unica_assimetrica_descarta_face_a_face(db_session):
    lote = _lote(db_session)
    moldes = [_molde(db_session, "FRENTE", RETANGULO, "simples"), _molde(db_session, "BOLSO", L, "simples")]
    _, _, d = _decidir(db_session, lote, moldes)
    assert d.tipo == MESMA_FACE and not d.face_a_face_valida
    assert "assimétrica" in d.motivo and d.regra == "FACE_A_FACE_INVALIDA"


def test_tempo_esgotado_usa_padrao_seguro(db_session):
    lote = _lote(db_session)
    moldes = [_molde(db_session, "FRENTE", RETANGULO, "simples"), _molde(db_session, "MANGA", L, "par")]
    grupos = svc._agrupar_por_lote([(lote, m, 4) for m in moldes])
    tecido, moldes_qtd = grupos[lote.id]
    kw = {"semente": 0, "cache": {}, "prazo": 0.0, "progresso": None}  # prazo já passou

    d = svc._decidir_lote(tecido, moldes_qtd, 150, tipo_fixo=None, modo_fixo=None, **kw)
    assert (d.tipo, d.modo) == (MESMA_FACE, "SEM_SOBRA")
    assert d.tempo_esgotado and d.regra == "PADRAO_SEGURO"
    assert "passou de" in d.motivo and not any(c.avaliado for c in d.candidatos)

    # com face a face fixada no Avançado, o padrão seguro respeita a escolha
    d = svc._decidir_lote(tecido, moldes_qtd, 150, tipo_fixo=FACE_A_FACE, modo_fixo=None, **kw)
    assert (d.tipo, d.modo) == (FACE_A_FACE, "SEM_SOBRA")

    # o motivo do prazo é o que a OC passou, não um relógio genérico
    kw["motivo_prazo"] = "o perfil mais barato já está em 306 s estimados"
    d = svc._decidir_lote(tecido, moldes_qtd, 150, tipo_fixo=None, modo_fixo=None, **kw)
    assert "306 s estimados" in d.motivo


# ── A comparação tem orçamento: é uma fatia do limite da OC ───────────────


def _custos(db, lote, moldes, qtd=4):
    grupos = svc._agrupar_por_lote([(lote, m, qtd) for m in moldes])
    tecido, moldes_qtd = grupos[lote.id]
    lista = decisor.candidatos(svc._analisar_lote(tecido, moldes_qtd), None, None)
    return svc._custos_candidatos(tecido, moldes_qtd, 150, lista)


def test_candidato_que_nao_cabe_no_prazo_e_pulado_mas_a_decisao_usa_o_que_rodou(db_session):
    # Face a face com peça em par duplica as alternativas; com o prazo cortado
    # no meio, só as mais baratas simulam — e a meia comparação ainda decide,
    # dizendo na tela o que ficou de fora.
    lote = _lote(db_session)
    moldes = [_molde(db_session, "FRENTE", RETANGULO, "simples"), _molde(db_session, "MANGA", L, "par")]
    grupos = svc._agrupar_por_lote([(lote, m, 4) for m in moldes])
    tecido, moldes_qtd = grupos[lote.id]
    custos = _custos(db_session, lote, moldes)
    assert len(custos) > 1
    fila = sorted(range(len(custos)), key=lambda i: (custos[i], i))
    kw = {"semente": 0, "cache": {}, "progresso": None, "custos": custos}

    # prazo cortado no meio da fila
    d = svc._decidir_lote(
        tecido,
        moldes_qtd,
        150,
        tipo_fixo=None,
        modo_fixo=None,
        prazo=time.monotonic() + custos[fila[0]] * 1.2,
        **kw,
    )
    rodaram = [i for i, c in enumerate(d.candidatos) if c.avaliado and c.erro is None]
    # o que rodou é exatamente o início mais barato da fila — nunca um pulo,
    # e nunca um candidato caro escolhido porque o barato não coube
    assert rodaram == fila[: len(rodaram)]
    assert rodaram, "a meia comparação tem de decidir alguma coisa"
    assert len(rodaram) < len(custos), "o teste precisa de um prazo que corte a fila"
    for i in fila[len(rodaram) :]:
        # o que ficou de fora não chegou a rodar o motor, e é nomeado no motivo
        assert d.candidatos[i].segundos == 0.0
        assert d.candidatos[i].rotulo.lower() in d.motivo
    assert d.tempo_esgotado and d.regra != "PADRAO_SEGURO"
    assert "Comparação incompleta por falta de tempo" in d.motivo

    # prazo que não cobre nem o mais barato: padrão seguro, como sempre
    d = svc._decidir_lote(tecido, moldes_qtd, 150, tipo_fixo=None, modo_fixo=None, prazo=time.monotonic(), **kw)
    assert d.regra == "PADRAO_SEGURO" and not any(c.avaliado for c in d.candidatos)


def test_orcamento_da_comparacao_vem_do_limite_da_oc(db_session, monkeypatch):
    # O piso do pedido (o plano mais barato possível, sem rodar o motor) é o
    # que o limite da OC tem que pagar. O que sobrar é o que a comparação
    # pode gastar. Medido na OC-0004: piso 306 s contra limite de 300 s — não
    # sobrava nada, e comparar de qualquer jeito custava 180 s para chegar ao
    # padrão seguro, que é o que a comparação escolheria de novo.
    vistos: list[float] = []
    original = svc._custos_candidatos

    def _spy(tecido, moldes_qtd, limite_cm, lista):
        custos = original(tecido, moldes_qtd, limite_cm, lista)
        vistos.append(min(custos, default=0.0))
        return custos

    monkeypatch.setattr(svc, "_custos_candidatos", _spy)
    lote = _lote(db_session)
    moldes = [_molde(db_session, "FRENTE", RETANGULO, "simples"), _molde(db_session, "MANGA", L, "par")]
    grupos = svc._agrupar_por_lote([(lote, m, 4) for m in moldes])

    # limite menor que o piso: nada de comparação, e o motivo explica por quê
    _, _, _, decisoes = svc._montar_todos(
        None, grupos, "AUTOMATICO", None, None, 150, "RAPIDO", None, tempo_maximo_s=0.5
    )
    d = decisoes[str(lote.id)]
    assert vistos, "o piso tem de ser estimado antes de comparar"
    assert d.regra == "PADRAO_SEGURO" and not any(c.avaliado for c in d.candidatos)
    assert "não sobrou tempo para comparar" in d.motivo
    assert f"{vistos[0]:.0f} s estimados" in d.motivo
    # o limite aparece como ele é — 0,5 s arredondado para "0 s" mentiria
    assert "limite de 0.5 s" in d.motivo


def test_comparacao_ganha_somente_a_folga_do_limite(db_session, monkeypatch):
    # Com folga, a comparação roda — mas nunca passa do teto do decisor, mesmo
    # que o limite da OC seja enorme.
    capturado: dict = {}
    original = svc._decidir_lote

    def _spy(*a, **kw):
        capturado["prazo"] = kw["prazo"]
        return original(*a, **kw)

    monkeypatch.setattr(svc, "_decidir_lote", _spy)
    lote = _lote(db_session)
    moldes = [_molde(db_session, "FRENTE", RETANGULO, "simples")]
    grupos = svc._agrupar_por_lote([(lote, m, 4) for m in moldes])
    piso = min(_custos(db_session, lote, moldes))

    t0 = time.monotonic()
    svc._montar_todos(None, grupos, "AUTOMATICO", None, None, 150, "RAPIDO", None, tempo_maximo_s=10_000)
    sobra = capturado["prazo"] - t0
    assert sobra <= decisor.TEMPO_COMPARACAO_S + 1.0
    assert sobra == pytest.approx(decisor.TEMPO_COMPARACAO_S, abs=1.0)

    t0 = time.monotonic()
    svc._montar_todos(None, grupos, "AUTOMATICO", None, None, 150, "RAPIDO", None, tempo_maximo_s=piso + 40)
    sobra = capturado["prazo"] - t0
    # metade da folga, e nunca mais que o teto
    assert sobra <= min(decisor.TEMPO_COMPARACAO_S, 20.0) + 1.0


def test_so_o_vencedor_conta_como_piso_pago(db_session):
    # A comparação roda candidatos que são DESCARTADOS — o tempo deles foi
    # gasto de verdade e tem de pesar no limite do usuário. O que o orçamento
    # desconta é só o candidato vencedor, que é o único reaproveitado do cache
    # na geração (mesmo lote, tipo/modo, semente e limite).
    lote = _lote(db_session)
    moldes = [_molde(db_session, "FRENTE", RETANGULO, "simples"), _molde(db_session, "MANGA", L, "par")]
    grupos = svc._agrupar_por_lote([(lote, m, 4) for m in moldes])
    piso = min(_custos(db_session, lote, moldes))

    encaixes, _, _, decisoes = svc._montar_todos(
        None, grupos, "AUTOMATICO", None, None, 150, svc.QUALIDADE_PADRAO, None, tempo_maximo_s=piso + 400
    )
    d = decisoes[str(lote.id)]
    avaliados = [c for c in d.candidatos if c.avaliado and c.erro is None]
    assert len(avaliados) > 1, "o teste precisa de comparação com mais de um candidato"
    vencedor = next(c for c in avaliados if (c.tipo, c.modo) == (d.tipo, d.modo))
    gasto = sum(c.segundos for c in avaliados)

    detalhes = [e.mapa_json["qualidade_automatica"] for e in encaixes if "qualidade_automatica" in e.mapa_json]
    assert detalhes, "a qualidade Automático tem de registrar o porquê do perfil"
    # o detalhe vai para o documento, em segundos inteiros
    pago = detalhes[0]["piso_pago_s"]
    assert pago == round(vencedor.segundos)
    assert pago < gasto, "tempo de candidato descartado não pode virar piso pago"


def test_decide_todos_os_lotes_antes_de_encaixar(db_session, monkeypatch):
    # O prazo da comparação não pode ser consumido pelo encaixe definitivo
    # de um lote anterior: todas as decisões vêm antes de qualquer encaixe.
    # E a decisão começa pelo lote MAIS BARATO de comparar — é o que impede o
    # tempo de acabar no primeiro da lista e o resto cair no padrão.
    ordem = []

    def _decidir(tecido, *a, **kw):
        ordem.append(("decide", tecido.lote_id))
        return decisor.Decisao(tipo=MESMA_FACE, modo="SEM_SOBRA", motivo="", regra="")

    def _gerar(pedido, tecido, *a, **kw):
        ordem.append(("encaixa", tecido.lote_id))
        return [], [], {"enfestos": [], "sobra_total": 0}

    monkeypatch.setattr(svc, "_decidir_lote", _decidir)
    monkeypatch.setattr(svc, "_gerar_para_tecido", _gerar)
    grande = _lote(db_session)
    pequeno = _lote(db_session)
    m_grande = _molde(db_session, "FRENTE", RETANGULO, "simples")
    m_pequeno = _molde(db_session, "FRENTE", RETANGULO, "simples")
    g_grande = svc._agrupar_por_lote([(grande, m_grande, 40)])
    g_pequeno = svc._agrupar_por_lote([(pequeno, m_pequeno, 1)])
    # o lote grande vem PRIMEIRO na lista, como no cadastro real
    grupos = {grande.id: g_grande[grande.id], pequeno.id: g_pequeno[pequeno.id]}

    svc._montar_todos(None, grupos, "AUTOMATICO", None, None, 150, "RAPIDO", None)
    assert ordem == [
        ("decide", pequeno.id),
        ("decide", grande.id),
        ("encaixa", grande.id),
        ("encaixa", pequeno.id),
    ]
