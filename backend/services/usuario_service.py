import logging
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import settings
from models.usuario import Permissao, Usuario

logger = logging.getLogger("smartcut.auth")

_pwd_context = CryptContext(schemes=["bcrypt"])
_ALGORITHM = "HS256"
_EXPIRY_HOURS = 8

_DEFAULT_JWT_SECRET = "smartcut-dev-jwt-secret-CHANGE-ME"
if settings.jwt_secret_key == _DEFAULT_JWT_SECRET:
    logger.warning(
        "JWT_SECRET_KEY não definido em backend/.env — usando chave padrão de "
        "desenvolvimento. Defina JWT_SECRET_KEY antes de ir para produção."
    )


# ── Senha ────────────────────────────────────────────────────────────────

def hash_senha(senha: str) -> str:
    return _pwd_context.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return _pwd_context.verify(senha, senha_hash)


# ── Token JWT (sistema administrativo — separado do JWT do vendedor) ──────

def criar_token(usuario: Usuario) -> str:
    payload = {
        "sub": str(usuario.id),
        "username": usuario.username,
        "is_admin": usuario.is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_EXPIRY_HOURS),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)


def decodificar_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[_ALGORITHM])


# ── Permissões ─────────────────────────────────────────────────────────

def listar_permissoes(db: Session, usuario_id: int) -> list[dict]:
    permissoes = (
        db.query(Permissao)
        .filter(Permissao.usuario_id == usuario_id, Permissao.permitido == True)
        .all()
    )
    return [{"modulo": p.modulo, "acao": p.acao} for p in permissoes]


def usuario_para_dict(db: Session, usuario: Usuario) -> dict:
    return {
        "id": usuario.id,
        "username": usuario.username,
        "nome_completo": usuario.nome_completo,
        "is_admin": usuario.is_admin,
        "permissoes": listar_permissoes(db, usuario.id),
    }
