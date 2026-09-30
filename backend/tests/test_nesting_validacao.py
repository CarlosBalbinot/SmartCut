"""Validação antes de encaixar (Tarefa 2), nova tentativa em caso de falha
(Tarefa 3) e qualidade Automática (Tarefa 4) — services/nesting_service.

Não roda o motor de verdade: o caminho de erro e a nova tentativa são testados
injetando `_montar_todos`, e a geometria dos moldes é feita direto no
geometria_json.
"""

import uuid
from datetime import date

import pytest

from models.molde import Molde
from models.tecido import CorTecido, LoteTecido, ModeloTecido
from services import nesting_service as svc
from services.nesting_service import ErroNesting, ErroPoligono
from services.planejamento import custo
from services.planejamento.custo import PERFIS

# Retângulo base: 40 cm de largura (eixo x) × 120 cm de comprimento (eixo y).
RETANGULO = [[0.0, 0.0], [40.0, 0.0], [40.0, 120.0], [0.0, 120.0]]


# ── Cenário ──────────────────────────────────────────────────────────────────


def _lote(db, largura_util=150.0, nome_cor="PRETO", codigo="LOTE-A") -> LoteTecido:
    modelo = ModeloTecido(nome="JACARANDA", tipo="Malha", max_camadas=15)
    db.add(modelo)
    db.commit()
    cor = CorTecido(
        modelo_id=modelo.id,
        nome_cor=nome_cor,
        largura_util_cm=largura_util,
        gramatura_g_m2=200.0,
        encolhimento_pct=0.0,
    )
    db.add(cor)
    db.commit()
    lote = LoteTecido(
        cor_id=cor.id,
        codigo_lote=codigo,
        peso_inicial_kg=50.0,
        peso_disponivel_kg=50.0,
        valor_kg=30.0,
        data_compra=date(2026, 1, 1),
    )
    db.add(lote)
    db.commit()
    db.refresh(cor)
    db.refresh(lote)
    return lote


def _molde(db, pontos=None, nome="CAMISA M", sentido_fio=None) -> Molde:
    if pontos is None:
        pontos = RETANGULO
    m = Molde(
        nome=nome,
        peca="FRENTE",
        tamanho="M",
        sentido_fio=sentido_fio,
        tipo_corte="simples",
        rotacao_base=0,
        geometria_json={"type": "Polygon", "coordinates": [pontos]},
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


# ── Qualidade Automática: por orçamento de tempo (Tarefa 4) ──────────────────


def test_automatico_e_o_padrao_e_os_perfis_fixos_continuam_valendo():
    from models.ordem_corte import QUALIDADES, QUALIDADE_PADRAO

    assert QUALIDADE_PADRAO == "AUTOMATICO"
    assert QUALIDADES == ("AUTOMATICO", "RAPIDO", "EQUILIBRADO", "MAXIMO")
    assert svc.QUALIDADES_PERFIS == QUALIDADES
    assert set(svc.QUALIDADES) == {"RAPIDO", "EQUILIBRADO", "MAXIMO"}
    # A regra antiga (≤ 80 peças → Máximo) não existe mais: o perfil sai do
    # orçamento de tempo, não da contagem de peças.
    assert not hasattr(svc, "_perfil_automatico")
    assert not hasattr(svc, "AUTO_PECAS_MAXIMO")
    assert svc.TEMPO_MAXIMO_OC_PADRAO_S == 300


def test_estimador_conta_o_preco_do_risco_em_segundos():
    # 30 peças / 5 mesas no perfil Rápido medem 45,7 s no motor (OC-0004);
    # a área dos 6 conjuntos (P1 M2 G2 GG1 do LEGGING FLARE) dá 5 mesas.
    area = 50972
    mesas = custo.estimar_mesas(area, 150, 150)
    assert mesas == 5
    rapido = custo.estimar_segundos(30, area, 150, 150)
    assert rapido > 45.7 * 0.9  # pessimista: nunca subestima o medido
    assert rapido < 45.7 * 1.3
    assert custo.estimar_segundos(30, area, 150, 150, "MAXIMO") > rapido * 6


def test_orcamento_sobe_um_risco_por_vez_a_partir_do_rapido():
    o = custo.Orcamento(300)
    for chave, pecas in (("a", 30), ("b", 25), ("c", 15), ("d", 5)):
        o.registrar(chave, pecas=pecas, area_cm2=pecas * 1700, largura_cm=150, limite_cm=150)
    atrib = o.distribuir()
    assert set(atrib) == {"a", "b", "c", "d"}
    assert all(p in PERFIS for p in atrib.values())
    # Nenhum risco sobe se o prazo mal dá para o Rápido (a OC-0004: 4,4 min).
    assert o.aviso is None
    assert o.total_rapido_s <= 300


def test_orcamento_da_sobra_ao_risco_mais_pesado():
    """A sobra sobe o risco com mais peças mesmo quando o tempo do degrau
    dele é maior que a soma de vários degraus dos riscos leves — senão o
    Encaixe Rápido de 5 peças sobe a Máximo e rouba o tempo do risco grande.
    Orçamento 220 s: sobra para o degrau do risco pesado (113,9 s) e não
    para o dele mais o do leve (12 s)."""
    o = custo.Orcamento(220)
    o.registrar("grosso", pecas=50, area_cm2=85000, largura_cm=130, limite_cm=150)
    o.registrar("fino", pecas=5, area_cm2=8500, largura_cm=150, limite_cm=150)
    atrib = o.distribuir()
    assert atrib["grosso"] == "EQUILIBRADO"
    assert atrib["fino"] == "RAPIDO"


def test_orcamento_sobe_um_degrau_por_vez_na_fila():
    """A sobra vai um degrau por vez, na fila dos mais pesados: no 350 s o
    risco de 50 peças sobe para Equilibrado (e NÃO para Máximo, que
    custaria 438 s), o de 30 também, e o de 5 fica no piso."""
    o = custo.Orcamento(350)
    o.registrar("grosso", pecas=50, area_cm2=85000, largura_cm=130, limite_cm=150)
    o.registrar("meio", pecas=30, area_cm2=51000, largura_cm=150, limite_cm=150)
    o.registrar("fino", pecas=5, area_cm2=8500, largura_cm=150, limite_cm=150)
    atrib = o.distribuir()
    assert atrib == {"grosso": "EQUILIBRADO", "meio": "EQUILIBRADO", "fino": "RAPIDO"}
    assert o.sobra_s > 0  # sobrou tempo e ninguém mais pôde usar


def test_orcamento_empate_no_pecas_vai_para_o_mais_carro():
    o = custo.Orcamento(150)
    o.registrar("largo", pecas=20, area_cm2=20000, largura_cm=150, limite_cm=150)
    o.registrar("estreito", pecas=20, area_cm2=60000, largura_cm=150, limite_cm=150)
    atrib = o.distribuir()
    assert atrib["estreito"] == "EQUILIBRADO"
    assert atrib["largo"] == "RAPIDO"


def test_orcamento_avisa_quando_o_piso_nao_cabe():
    o = custo.Orcamento(30)
    o.registrar("gigante", pecas=200, area_cm2=400000, largura_cm=150, limite_cm=150)
    atrib = o.distribuir()
    assert atrib["gigante"] == "RAPIDO"
    assert o.aviso is not None and "Rápido" in o.aviso


def test_orcamento_desconta_o_piso_ja_pago_pela_comparacao():
    """A comparação de enfesto roda o motor antes do orçamento existir; o que
    sobrou do limite do usuário é o que a geração pode gastar."""
    o = custo.Orcamento(300, piso_pago_s=180)
    assert o.disponivel_s == 120
    o.registrar("a", pecas=30, area_cm2=50972, largura_cm=150, limite_cm=150)
    atrib = o.distribuir()
    assert atrib["a"] == "RAPIDO"  # degrau Equilibrado (72 s) não cabe em 120 s
    assert o.aviso is None
    det = o.detalhe("a")
    assert det["piso_pago_s"] == 180
    assert det["orcamento_s"] == 300


def test_orcamento_avisa_quando_a_comparacao_sozinha_estourou_o_limite():
    o = custo.Orcamento(300, piso_pago_s=290)
    o.registrar("a", pecas=30, area_cm2=50972, largura_cm=150, limite_cm=150)
    assert o.disponivel_s == 10
    assert o.aviso is not None and "comparação de enfestos" in o.aviso


def test_aviso_sem_comparacao_nao_fala_de_comparacao():
    o = custo.Orcamento(30)
    o.registrar("a", pecas=200, area_cm2=400000, largura_cm=150, limite_cm=150)
    assert o.aviso is not None and "comparação de enfestos" not in o.aviso
    assert "30 s" in o.aviso

    # piso pago de menos de 1 s arredondaria para "já levou 0 s" — omitir
    o = custo.Orcamento(30, piso_pago_s=0.4)
    o.registrar("a", pecas=200, area_cm2=400000, largura_cm=150, limite_cm=150)
    assert o.aviso is not None and "comparação de enfestos" not in o.aviso


def test_orcamento_documenta_o_perfil_no_mapa():
    o = custo.Orcamento(300)
    o.registrar("x", pecas=30, area_cm2=50972, largura_cm=150, limite_cm=150)
    o.distribuir()
    det = o.detalhe("x")
    assert det["perfil"] in PERFIS
    assert det["pecas"] == 30
    assert det["mesas_estimadas"] == 5
    assert det["segundos_estimados"] > 0
    assert det["orcamento_s"] == 300
    assert "300 s" in det["regra"]
    assert o.detalhe("nao-registrado") == {}


# ── Polígono inválido: reparo automático ou bloqueio (Tarefa 2) ─────────────


def test_poligono_autointersectado_e_corrigido():
    # Casca de quatro pontos em que o anel se cruza (bowtie): o shoelace dá
    # zero, mas o polígono tem duas metades legítimas — o reparo tem de
    # acontecer antes do teste de área.
    pontos = [[0.0, 0.0], [40.0, 120.0], [40.0, 0.0], [0.0, 120.0]]
    anel = svc._sanear_poligono(pontos, "CAMISA M")
    assert len(anel) >= 3
    assert svc._area(anel) > 1e-6


def test_poligono_valido_passa_sem_mudar_a_area():
    anel = svc._sanear_poligono(RETANGULO, "CAMISA M")
    assert svc._area(anel) == pytest.approx(40 * 120)


def test_poligono_com_menos_de_3_pontos_bloqueia_citando_o_molde():
    with pytest.raises(ErroPoligono) as exc:
        svc._sanear_poligono([[0.0, 0.0], [10.0, 0.0]], "SAQUINHO")
    assert "SAQUINHO" in str(exc.value)


def test_poligono_de_area_zero_bloqueia_citando_o_molde():
    pontos = [[0.0, 0.0], [10.0, 0.0], [5.0, 0.0]]
    with pytest.raises(ErroPoligono) as exc:
        svc._sanear_poligono(pontos, "SAQUINHO")
    assert "SAQUINHO" in str(exc.value)


def test_molde_sem_geometria_usa_o_retangulo_pela_area(db_session):
    m = Molde(nome="SEM GEO", peca="FRENTE", tamanho="M", tipo_corte="simples", area_cm2=400.0)
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    assert svc._area(svc._poligono(m)) == pytest.approx(400.0, rel=1e-3)


# ── Largura útil e limite de mesa (Tarefa 2) ─────────────────────────────────


def test_peca_mais_larga_que_a_largura_util_bloqueia_citando_molde_e_tecido(db_session):
    lote = _lote(db_session, largura_util=35.0)  # a peça tem 40 cm
    molde = _molde(db_session, nome="CAMISA M")

    achados = svc.checar_molde(molde, lote, comprimento_max_cm=150)

    assert [c for c, _m, _b in achados] == ["PECA_LARGURA_UTIL"]
    assert achados[0][2] is True  # bloqueia
    msg = achados[0][1]
    assert "CAMISA M" in msg and "JACARANDA" in msg and "PRETO" in msg


def test_largura_ok_nao_bloqueia(db_session):
    lote = _lote(db_session, largura_util=130.0)  # peça 40 x 120
    molde = _molde(db_session, nome="CAMISA M")
    assert svc.checar_molde(molde, lote, comprimento_max_cm=150) == []


def test_peca_mais_comprida_que_a_mesa_avisa_sem_bloquear(db_session):
    lote = _lote(db_session, largura_util=150.0)
    # Fio vertical (só 0°/180°): os 120 cm continuam no eixo do comprimento.
    molde = _molde(db_session, sentido_fio="vertical")

    achados = svc.checar_molde(molde, lote, comprimento_max_cm=100)

    assert [c for c, _m, _b in achados] == ["PECA_LIMITE_MESA"]
    assert achados[0][2] is False  # não bloqueia
    assert "ATENÇÃO" in achados[0][1] and "CAMISA M" in achados[0][1]


def test_giro_livre_resolve_o_comprimento_da_mesa(db_session):
    """Sem sentido de fio a peça pode virar de lado: 120 vira 40 no eixo do
    comprimento e deixa de estourar a mesa."""
    lote = _lote(db_session, largura_util=150.0)
    assert svc.checar_molde(_molde(db_session), lote, comprimento_max_cm=100) == []


def test_sentido_do_fio_decide_se_a_peca_passa_da_largura_util(db_session):
    # Peça 40 x 120 com 100 cm de largura útil: deitada (0°/180°, fio vertical)
    # a largura pedida é 40; em pé (90°/270°, fio horizontal) é 120 — não entra.
    lote = _lote(db_session, largura_util=100.0)
    assert [c for c, _m, _b in svc.checar_molde(_molde(db_session, sentido_fio="vertical"), lote, 150)] == []

    bloqueia = svc.checar_molde(_molde(db_session, nome="CAMISA H", sentido_fio="horizontal"), lote, 150)
    assert [c for c, _m, b in bloqueia] == ["PECA_LARGURA_UTIL"]
    assert bloqueia[0][2] is True


def test_sem_lote_nao_ha_o_que_checar(db_session):
    molde = _molde(db_session)
    assert svc.checar_molde(molde, None, comprimento_max_cm=150) == []


def test_validar_entradas_separa_bloqueio_de_aviso_e_deduplica(db_session):
    lote_estreito = _lote(db_session, largura_util=30.0)
    largo = _molde(db_session, nome="LARGO")  # 40 x 120
    entradas = [(lote_estreito, largo, 2), (lote_estreito, largo, 3)]

    problemas, avisos = svc.validar_entradas(entradas, comprimento_max_cm=150)

    assert len(problemas) == 1 and "LARGO" in problemas[0]  # repetido aparece uma vez
    assert avisos == []

    lote_ok = _lote(db_session, largura_util=150.0, nome_cor="VERDE", codigo="LOTE-B")
    alto = _molde(db_session, nome="ALTO", sentido_fio="vertical")  # 120 cm no comprimento
    problemas2, avisos2 = svc.validar_entradas([(lote_ok, alto, 1)], comprimento_max_cm=100)
    assert problemas2 == []
    assert len(avisos2) == 1 and "ATENÇÃO" in avisos2[0]


def test_config_producao_nao_tem_mais_motor_de_encaixe(db_session):
    cfg = svc.config_producao(db_session)
    assert "motor_encaixe" not in cfg
    assert set(cfg) == {"comprimento_max_mesa_cm", "alerta_economia_pct", "tempo_maximo_oc_s"}
    assert cfg["tempo_maximo_oc_s"] == 300


def test_api_configura_o_tempo_limite_da_ordem_de_corte(client, headers_admin, db_session):
    """O limite do orçamento de qualidade é cadastrado em Configurações >
    Produção e volta na leitura."""
    url = "/api/v1/ordens-corte/configuracao-producao"
    antes = client.get(url, headers=headers_admin)
    assert antes.status_code == 200
    assert antes.json()["data"]["tempo_maximo_oc_s"] == 300

    res = client.patch(url, json={"tempo_maximo_oc_s": 600}, headers=headers_admin)
    assert res.status_code == 200
    assert res.json()["data"]["tempo_maximo_oc_s"] == 600
    assert client.get(url, headers=headers_admin).json()["data"]["tempo_maximo_oc_s"] == 600


@pytest.mark.parametrize("valor", [0, 29, 7201, 90.5, "abc"])
def test_api_recusa_tempo_limite_fora_da_faixa(client, headers_admin, valor):
    res = client.patch(
        "/api/v1/ordens-corte/configuracao-producao",
        json={"tempo_maximo_oc_s": valor},
        headers=headers_admin,
    )
    assert res.status_code == 422


def test_agrupamento_soma_a_mesma_peca_de_itens_diferentes(db_session):
    lote = _lote(db_session)
    molde = _molde(db_session)
    assert isinstance(uuid.UUID(str(molde.id)), uuid.UUID)
    grupos = svc._agrupar_por_lote([(lote, molde, 2), (lote, molde, 3)])
    assert list(grupos) == [lote.id]
    assert grupos[lote.id][0].largura_util_cm == 150.0
    assert grupos[lote.id][1][molde.id][1] == 5  # soma as duas entradas


# ── Nova tentativa e erro claro (Tarefa 3) ───────────────────────────────────


class _DbFalso:
    """Só o que gerar_de_entradas usa da sessão."""

    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1

    def add(self, obj):
        pass

    def flush(self):
        pass

    def commit(self):
        pass


def test_falha_enta_com_nova_tentativa_de_outra_semente_e_perfil_rapido(db_session, monkeypatch):
    lote = _lote(db_session)
    molde = _molde(db_session)
    chamadas = []

    def _falha_uma_vez(pedido, grupos, modo, oc, desc, limite, qualidade, progresso, semente=0, **_kw):
        chamadas.append((qualidade, semente))
        if len(chamadas) == 1:
            raise RuntimeError("spyrrow explodiu")
        return [], [], {}, {}

    monkeypatch.setattr(svc, "_montar_todos", _falha_uma_vez)
    monkeypatch.setattr(svc, "_gravar", lambda db, encaixes: None)

    r = svc.gerar_de_entradas(_DbFalso(), None, [(lote, molde, 1)], modo="SEM_SOBRA", qualidade="MAXIMO")

    assert chamadas == [("MAXIMO", 0), ("RAPIDO", 1)]  # tentativa original + a nova
    assert r["motor_usado"] == "v2"
    assert r["encaixes"] == []


def test_segunda_falha_vira_erro_nesting_e_nada_e_gravado(db_session, monkeypatch):
    lote = _lote(db_session)
    molde = _molde(db_session)
    chamadas, gravados = [], []

    def _sempre_falha(pedido, grupos, modo, oc, desc, limite, qualidade, progresso, semente=0, **_kw):
        chamadas.append((qualidade, semente))
        raise RuntimeError("sem memória")

    monkeypatch.setattr(svc, "_montar_todos", _sempre_falha)
    monkeypatch.setattr(svc, "_gravar", lambda db, encaixes: gravados.append(encaixes))
    db_falso = _DbFalso()

    with pytest.raises(ErroNesting) as exc:
        svc.gerar_de_entradas(db_falso, None, [(lote, molde, 1)], modo="SEM_SOBRA")

    assert len(chamadas) == 2  # exatamente 2 tentativas (nada de laço infinito)
    assert str(exc.value) == "sem memória"
    assert gravados == []
    assert db_falso.rollbacks == 1


def test_cancelamento_nao_vira_nova_tentativa(db_session, monkeypatch):
    lote = _lote(db_session)
    molde = _molde(db_session)
    chamadas = []

    def _cancelar(pedido, grupos, modo, oc, desc, limite, qualidade, progresso, semente=0, **_kw):
        chamadas.append(semente)
        raise svc.GeracaoCancelada("usuário cancelou")

    monkeypatch.setattr(svc, "_montar_todos", _cancelar)

    with pytest.raises(svc.GeracaoCancelada):
        svc.gerar_de_entradas(_DbFalso(), None, [(lote, molde, 1)], modo="SEM_SOBRA")

    assert chamadas == [0]  # uma única chamada


def test_motor_nao_instalado_da_mensagem_de_reinstalar(db_session, monkeypatch):
    lote = _lote(db_session)
    molde = _molde(db_session)
    monkeypatch.setattr(svc.nesting_v2, "DISPONIVEL", False)
    db_falso = _DbFalso()

    with pytest.raises(ErroNesting) as exc:
        svc.gerar_de_entradas(db_falso, None, [(lote, molde, 1)], modo="SEM_SOBRA")

    assert str(exc.value) == "Motor de encaixe não instalado corretamente. Reinstale o SmartCut."
    assert db_falso.rollbacks == 1


def test_nenhuma_entrada_com_quantidade_e_erro_de_legibilidade(db_session):
    lote = _lote(db_session)
    molde = _molde(db_session)
    with pytest.raises(ValueError) as exc:
        svc.gerar_de_entradas(_DbFalso(), None, [(lote, molde, 0)], modo="SEM_SOBRA")
    assert "Nenhuma peça" in str(exc.value)
