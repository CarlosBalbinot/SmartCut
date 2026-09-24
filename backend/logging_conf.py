"""logging_conf.py — Configuração central de logs (Parte 9.2).

Formato estruturado por linha:
    timestamp | nível | módulo | request_id | mensagem

O request_id é gerado por requisição HTTP no middleware ASGI e exposto:
    - nas logs (via filtro/contextvar) — correlação de erros em produção;
    - no header de resposta "X-Request-ID" — suporte/usuário repassa o id.

Regras de conteúdo (critério de aceitação da 9.2):
    - exceções internas são logadas completas (traceback, exc_info);
    - NUNCA são logados dados sensíveis: senhas, tokens de acesso, conteúdo
      de certificados digitais (.pfx/.p12) ou chaves de cifragem.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

# Valor por request; "-" quando fora de uma requisição (boot, testes, tasks).
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_FORMATO = "%(asctime)s | %(levelname)-8s | %(name)s | request_id=%(request_id)s | %(message)s"

# Loggers do uvicorn que precisam renderizar pelo formato unificado.
_LOGGERS_UVICORN = ("uvicorn", "uvicorn.error", "uvicorn.access")


class RequestIdFilter(logging.Filter):
    """Injeta o request_id da contextvar em cada registro de log."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def instalar_logging(level: int = logging.INFO) -> None:
    """Configura o logging do processo. Chamada na importação do main.py.

    - Handler único no logger raiz com o formato estruturado (filtro incluso).
    - Os loggers do uvicorn passam a propagar para o raiz — nada de formato
      duplicado; os níveis originais são preservados por herança.
    """
    raiz = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_FORMATO, datefmt="%Y-%m-%dT%H:%M:%S%z"))
    # O filtro fica no HANDLER (não só no logger raiz): registros propagados
    # de qualquer módulo (services, routers, alembic…) só passam pelos filtros
    # dos handlers — sem isso o request_id viraria "-" nos logs internos.
    handler.addFilter(RequestIdFilter())
    raiz.handlers = [handler]
    raiz.setLevel(level)
    raiz.addFilter(RequestIdFilter())  # cobre logs emitidos diretamente no raiz

    for nome in _LOGGERS_UVICORN:
        lg = logging.getLogger(nome)
        lg.handlers = []
        lg.propagate = True


class RequestIdMiddleware:
    """ASGI middleware: gera um request_id por requisição e o expõe.

    Implementação ASGI pura (sem BaseHTTPMiddleware) para garantir que a
    contextvar seja a mesma em todo o ciclo da requisição, incluindo o handler
    de exceções e os services chamados por dentro.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rid = uuid.uuid4().hex[:12]
        request_id_var.set(rid)

        async def send_com_header(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", rid.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_com_header)
