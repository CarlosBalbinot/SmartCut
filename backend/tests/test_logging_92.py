"""Testes da Parte 9.2 — logging estruturado e request_id (middleware ASGI).

Cobre o critério de aceitação:
    - linha de log estruturada com timestamp, nível, módulo e request_id;
    - erro interno rastreável: traceback completo no log + header X-Request-ID
      na resposta 500 (nunca a exceção crua no corpo);
    - nenhum dado sensível logado (aqui verificamos o formato e o vazamento do
      corpo do erro; conteúdo de arquivos segue documentado no Electron).
"""

from __future__ import annotations

import io
import logging

import pytest
from fastapi.testclient import TestClient

from logging_conf import RequestIdFilter, _FORMATO, request_id_var


def _handler_captura():
    """Handler espelho do de produção (formato + filtro), gravando em buffer."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter(_FORMATO, datefmt="%Y-%m-%dT%H:%M:%S%z"))
    handler.addFilter(RequestIdFilter())
    return handler, buf


@pytest.fixture()
def logs_capturados():
    """Substitui o handler raiz por um de captura durante o teste (restaura ao final)."""
    raiz = logging.getLogger()
    antigos = raiz.handlers
    handler, buf = _handler_captura()
    raiz.handlers = [handler]
    try:
        yield buf
    finally:
        raiz.handlers = antigos


def test_formato_estruturado_inclui_request_id(logs_capturados):
    request_id_var.set("abc123deadbe")
    logging.getLogger("services.teste_9_2").info("mensagem de teste simples")

    texto = logs_capturados.getvalue()
    assert "request_id=abc123deadbe" in texto, texto
    assert "| INFO" in texto, texto
    assert "| services.teste_9_2 |" in texto, texto


def test_middleware_request_id_por_request(app):
    with TestClient(app) as client:
        r1 = client.get("/health")
        r2 = client.get("/health")

    rid1 = r1.headers.get("x-request-id")
    rid2 = r2.headers.get("x-request-id")
    assert r1.status_code == 200
    assert rid1 and rid2
    assert rid1 != rid2  # cada requisição tem um id próprio


def test_erro_500_rastreavel_com_request_id_e_sem_vazamento(app, logs_capturados):
    # Rota temporária que levanta exceção não tratada (removida ao final).
    n_antes = len(app.routes)

    @app.get("/_boom-9-2")
    def boom():
        # Valor sensível (ex.: senha de certificado) em variável local — não
        # deve aparecer no log nem no corpo. A mensagem da exceção é genérica
        # e só expõe o tamanho do valor (referência p/ não virar F841).
        senha_certificado = "senha_super_secreta_valor"
        raise ValueError(f"erro interno de teste (sem dado sensível; len={len(senha_certificado)})")

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/_boom-9-2")
    finally:
        del app.routes[n_antes:]

    # Resposta: envelope genérico PT-BR + header com o id de correlação.
    assert resp.status_code == 500
    assert resp.json() == {"data": None, "error": "Erro interno"}
    rid = resp.headers.get("x-request-id")
    assert rid, resp.headers

    # Log: a MESMA linha do request tem o id, o traceback completo e o nome do
    # módulo — é isso que torna o erro de produção rastreável.
    texto = logs_capturados.getvalue()
    assert f"request_id={rid}" in texto, texto
    assert "Erro interno não tratado" in texto, texto
    assert "| main |" in texto, texto
    assert "len=25)" in texto, texto  # mensagem da exceção presente no traceback
    # O corpo da resposta NUNCA devolve a exceção crua, e valores sensíveis em
    # variáveis locais não entram no log (senhas/tokens/certificados).
    assert "senha_super_secreta_valor" not in resp.text, resp.text
    assert "senha_super_secreta_valor" not in texto, texto
