"""Formato único dos erros da API (F0, passo 5a).

Toda resposta de erro sai assim:

    {"data": null,
     "error": {"codigo": "OC_STATUS_MUDOU", "params": {...}, "mensagem": "<pt>"},
     "detail": "<pt>"}

- ``codigo``: estável, em maiúsculas — a tela decide pelo código, não pelo
  texto (e os idiomas traduzem a partir dele com os ``params``).
- ``mensagem``: texto em português, sempre presente (é o fallback).
- ``detail``: a mesma mensagem em texto, para quem ainda lê ``detail``
  (Financeiro, painel do vendedor, testes antigos). Na validação do pydantic
  continua sendo a lista de erros, como antes.

Regra de negócio violada → ``raise ErroApp("CODIGO", "mensagem", status, **params)``.
``HTTPException`` com texto continua valendo e sai com ``codigo: "ERRO"``.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Códigos genéricos (os específicos nascem junto de cada regra).
ERRO = "ERRO"
DADOS_INVALIDOS = "DADOS_INVALIDOS"
ERRO_INTERNO = "ERRO_INTERNO"

MSG_DADOS_INVALIDOS = "Dados inválidos. Verifique os campos."
MSG_ERRO_INTERNO = "Erro interno"


class ErroApp(Exception):
    """Erro de negócio com código estável (router/handler → HTTP `status`)."""

    def __init__(self, codigo: str, mensagem: str, status: int = 400, **params: Any):
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.status = status
        self.params = params


def corpo_erro(codigo: str, mensagem: str, params: dict | None = None, detail: Any = None) -> dict:
    """Corpo JSON de um erro; ``detail`` padrão = a própria mensagem."""
    return {
        "data": None,
        "error": {"codigo": codigo, "params": params or {}, "mensagem": mensagem},
        "detail": mensagem if detail is None else detail,
    }


def _erro_app(request: Request, exc: ErroApp) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content=jsonable_encoder(corpo_erro(exc.codigo, exc.mensagem, exc.params)),
    )


def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # detail em texto (o caso normal) vira a mensagem; outro formato segue
    # em `detail` como estava, com mensagem genérica.
    if isinstance(exc.detail, str):
        corpo = corpo_erro(ERRO, exc.detail)
    else:
        corpo = corpo_erro(ERRO, f"Erro {exc.status_code}", detail=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(corpo),
        headers=getattr(exc, "headers", None),
    )


def _validacao(request: Request, exc: RequestValidationError) -> JSONResponse:
    erros = exc.errors()
    # loc = ("body", "itens", 0, "qtd") → "itens.0.qtd" (a origem sai).
    campos = [".".join(str(p) for p in e["loc"][1:]) for e in erros]
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(corpo_erro(DADOS_INVALIDOS, MSG_DADOS_INVALIDOS, {"campos": campos}, detail=erros)),
    )


def registrar_handlers(app: FastAPI) -> None:
    """Handlers de ErroApp, HTTPException e validação. O de exceção não
    tratada (500) fica em main.py, junto do log com o traceback."""
    app.add_exception_handler(ErroApp, _erro_app)
    app.add_exception_handler(StarletteHTTPException, _http)
    app.add_exception_handler(RequestValidationError, _validacao)
