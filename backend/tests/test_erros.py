"""F0 passo 5a: formato único dos erros da API (services/erros.py).

{"data": null, "error": {"codigo", "params", "mensagem"}, "detail": mensagem}
— o `detail` em texto mantém quem ainda lê `detail` funcionando.
"""

import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from services.erros import ErroApp
from services.nesting_jobs import ErroJob
from services.nesting_service import ErroNesting
from services.ordem_corte_service import ErroOC


class _Corpo(BaseModel):
    nome: str
    qtd: int


@pytest.fixture()
def cliente_rotas(app):
    """App real (lifespan desligado) com rotas temporárias que levantam cada
    tipo de erro."""
    n_antes = len(app.routes)

    @app.get("/_erro-app")
    def erro_app():
        raise ErroApp("OC_STATUS_MUDOU", "A OC mudou de status.", 409, status_atual="ENVIADA")

    @app.get("/_erro-http")
    def erro_http():
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    @app.get("/_erro-http-headers")
    def erro_http_headers():
        raise HTTPException(status_code=401, detail="Não autenticado", headers={"WWW-Authenticate": "Bearer"})

    @app.get("/_erro-oc")
    def erro_oc():
        raise ErroOC("Ordem de Corte não encontrada", 404)

    @app.post("/_erro-validacao")
    def erro_validacao(corpo: _Corpo):
        return {"data": corpo.model_dump(), "error": None}

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        del app.routes[n_antes:]


def test_erro_app_codigo_params_e_detail(cliente_rotas):
    res = cliente_rotas.get("/_erro-app")
    assert res.status_code == 409
    assert res.json() == {
        "data": None,
        "error": {
            "codigo": "OC_STATUS_MUDOU",
            "params": {"status_atual": "ENVIADA"},
            "mensagem": "A OC mudou de status.",
        },
        "detail": "A OC mudou de status.",
    }


def test_http_exception_com_texto_vira_codigo_erro(cliente_rotas):
    res = cliente_rotas.get("/_erro-http")
    assert res.status_code == 404
    assert res.json() == {
        "data": None,
        "error": {"codigo": "ERRO", "params": {}, "mensagem": "Pedido não encontrado"},
        "detail": "Pedido não encontrado",
    }


def test_http_exception_mantem_headers(cliente_rotas):
    res = cliente_rotas.get("/_erro-http-headers")
    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"
    assert res.json()["detail"] == "Não autenticado"


def test_rota_inexistente_no_mesmo_formato(cliente_rotas):
    res = cliente_rotas.get("/_rota-que-nao-existe")
    assert res.status_code == 404
    assert res.json()["error"]["codigo"] == "ERRO"
    assert res.json()["detail"] == "Not Found"


def test_validacao_mantem_lista_no_detail(cliente_rotas):
    res = cliente_rotas.post("/_erro-validacao", json={"nome": "X", "qtd": "muitas"})
    assert res.status_code == 422
    corpo = res.json()
    assert corpo["error"]["codigo"] == "DADOS_INVALIDOS"
    assert corpo["error"]["mensagem"] == "Dados inválidos. Verifique os campos."
    assert corpo["error"]["params"] == {"campos": ["qtd"]}
    # Lista do pydantic como antes (o frontend antigo lê detail[0].msg).
    assert isinstance(corpo["detail"], list)
    assert corpo["detail"][0]["loc"] == ["body", "qtd"]


def test_erro_oc_passa_pelo_handler(cliente_rotas):
    res = cliente_rotas.get("/_erro-oc")
    assert res.status_code == 404
    assert res.json()["error"] == {"codigo": "ERRO", "params": {}, "mensagem": "Ordem de Corte não encontrada"}
    assert res.json()["detail"] == "Ordem de Corte não encontrada"


def test_erros_de_servico_sao_erro_app():
    assert isinstance(ErroOC("x"), ErroApp)
    assert ErroOC("x").status == 400
    assert isinstance(ErroJob("x"), ErroApp)
    assert ErroJob("x").status == 409
    # ErroNesting continua RuntimeError (quem captura RuntimeError não muda).
    exc = ErroNesting("motor falhou")
    assert isinstance(exc, ErroApp) and isinstance(exc, RuntimeError)
    assert (exc.status, exc.mensagem, str(exc)) == (500, "motor falhou", "motor falhou")


def test_rota_real_da_oc(client, headers_admin):
    """ErroOC de verdade (OC inexistente) pelo router de Ordens de Corte."""
    res = client.post(f"/api/v1/ordens-corte/{uuid.uuid4()}/cancelar", headers=headers_admin)
    assert res.status_code == 404
    assert res.json()["error"]["codigo"] == "ERRO"
    assert res.json()["detail"] == "Ordem de Corte não encontrada"


def test_rota_real_do_job(client, headers_admin):
    """ErroJob de verdade (cancelar sem geração em andamento)."""
    res = client.post(f"/api/v1/ordens-corte/{uuid.uuid4()}/job/cancelar", headers=headers_admin)
    assert res.status_code == 404
    assert res.json()["error"]["mensagem"] == "Nenhuma geração de encaixes em andamento."
