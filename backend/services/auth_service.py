"""Autenticação central do SmartCut (item 1.2).

Módulo único de senha e JWT para os DOIS sistemas de login do projeto:
- Painel do vendedor  → tipo "vendedor", subject prefixado "ven:"
- Sistema administrativo → tipo "admin",   subject prefixado "adm:"

O segredo é o mesmo para os dois (settings.jwt_segredo — ver config.py),
mas o subject prefixado + claim "tipo" garantem que um token de um sistema
jamais seja aceito como válido no outro.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import threading
import uuid
from jwt import InvalidTokenError

from config import settings

_ALGORITHM = "HS256"
_EXPIRY_HOURS = 8

PREFIXO_SUB_VENDEDOR = "ven:"
PREFIXO_SUB_ADMIN = "adm:"

# Política mínima de senha (item 1.3).
SENHA_MINIMO_CARACTERES = 8


# ── Senha (implementação única — bcrypt puro) ────────────────────────────

def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except ValueError:
        # Hash malformado/nulo — trata como senha inválida, sem estourar 500.
        return False


def validar_politica_senha(senha: str) -> str | None:
    """Valida a política mínima de senha (item 1.3).

    Usada em cadastro (setup, criação de usuário), troca de senha e
    credenciais do vendedor. Retorna None quando a senha é aceitável, ou a
    mensagem PT-BR a exibir no erro 400.
    """
    if not senha or len(senha) < SENHA_MINIMO_CARACTERES:
        return f"A senha deve ter no mínimo {SENHA_MINIMO_CARACTERES} caracteres."
    return None


# ── Tokens JWT ─────────────────────────────────────────────────────────────

def _payload(sub: str, username: str, tipo: str, **extra) -> dict:
    return {
        "sub": sub,
        "username": username,
        "tipo": tipo,
        "jti": uuid.uuid4().hex,
        **extra,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_EXPIRY_HOURS),
    }


def criar_token_vendedor(vendedor_id, username: str) -> str:
    return jwt.encode(
        _payload(f"{PREFIXO_SUB_VENDEDOR}{vendedor_id}", username, "vendedor"),
        settings.jwt_segredo,
        algorithm=_ALGORITHM,
    )


def criar_token_admin(usuario) -> str:
    return jwt.encode(
        _payload(
            f"{PREFIXO_SUB_ADMIN}{usuario.id}",
            usuario.username,
            "admin",
            is_admin=usuario.is_admin,
        ),
        settings.jwt_segredo,
        algorithm=_ALGORITHM,
    )


# ── Revogação de sessão (jti) ─────────────────────────────────────────────
# Logout adiciona o jti do token à lista de revogados. Limitação documentada
# (item 1.3): mantida apenas em memória — ao reiniciar o backend, tokens
# revogados voltariam a ser aceitos até expirarem (8h). Para um controle
# persistente seria preciso versão de token em banco (fora do escopo atual).
_REVOGADOS: set[str] = set()
_REVOGADOS_LOCK = threading.Lock()


def revogar_token(jti: str) -> None:
    """Revoga o jti informado (tokens futuros com esse jti passam a falhar)."""
    if not jti:
        return
    with _REVOGADOS_LOCK:
        _REVOGADOS.add(jti)


def _token_esta_revogado(jti: str) -> bool:
    with _REVOGADOS_LOCK:
        return jti in _REVOGADOS


def verificar_token(token: str) -> dict:
    dados = jwt.decode(token, settings.jwt_segredo, algorithms=[_ALGORITHM])
    if _token_esta_revogado(dados.get("jti", "")):
        raise InvalidTokenError("Token revogado")
    return dados