from fastapi import Cookie, Header, HTTPException, status
from jwt import ExpiredSignatureError, InvalidTokenError

from services.auth_service import PREFIXO_SUB_VENDEDOR, verificar_token

# Nome do cookie de sessão do painel do vendedor (item 1.4).
COOKIE_VENDEDOR = "smartcut_vendedor_token"


def _extrair_token(authorization: str, cookie_valor: str) -> str:
    """Prefere o header Authorization (Electron/safeStorage); sem ele, aceita
    o cookie HttpOnly (navegador). Nenhuma das duas fontes → 401 genérico."""
    if authorization.startswith("Bearer "):
        return authorization[7:]
    if cookie_valor:
        return cookie_valor
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token não informado")


def get_vendedor_atual(
    authorization: str = Header(default=""),
    token_vendedor: str = Cookie(default="", alias="smartcut_vendedor_token"),
) -> str:
    token = _extrair_token(authorization, token_vendedor)
    try:
        payload = verificar_token(token)
    except (ExpiredSignatureError, InvalidTokenError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado ou inválido")

    # Itens 1.1/1.2: token de outro sistema (admin) não autentica no painel
    # do vendedor — claim "tipo" + subject prefixado "ven:".
    sub = str(payload.get("sub", ""))
    if payload.get("tipo") != "vendedor" or not sub.startswith(PREFIXO_SUB_VENDEDOR):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido para o painel do vendedor",
        )
    return sub[len(PREFIXO_SUB_VENDEDOR) :]
