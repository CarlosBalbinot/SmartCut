import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

_SECRET = os.getenv("SECRET_KEY", "change-me-in-production")
_ALGORITHM = "HS256"
_EXPIRY_HOURS = 8


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def verificar_senha(senha: str, hash: str) -> bool:
    return bcrypt.checkpw(senha.encode(), hash.encode())


def criar_token(vendedor_id: str, username: str) -> str:
    payload = {
        "sub": str(vendedor_id),
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_EXPIRY_HOURS),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def verificar_token(token: str) -> dict:
    return jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
