from fastapi import Header, HTTPException, status
from jwt import ExpiredSignatureError, InvalidTokenError

from services.auth_service import verificar_token


def get_vendedor_atual(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    token = authorization[7:]
    try:
        payload = verificar_token(token)
        return payload["sub"]
    except (ExpiredSignatureError, InvalidTokenError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado ou inválido")
