from typing import Optional

import jwt as pyjwt
from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.usuario import ACOES_VALIDAS, MODULOS_VALIDOS, Permissao, Usuario
from services.auth_service import PREFIXO_SUB_ADMIN, verificar_token


def get_current_user(
    authorization: Optional[str] = Header(None),
    token_admin: str = Cookie(default="", alias="smartcut_token"),
    db: Session = Depends(get_db),
) -> Usuario:
    """Dependency FastAPI: extrai o Bearer token (header no Electron, cookie
    HttpOnly no navegador), valida o JWT (sistema administrativo — mesmo
    segredo do painel do vendedor, diferenciado pela claim "tipo": admin e
    subject prefixado "adm:") e devolve o Usuario autenticado.

    Uso: current_user: Usuario = Depends(get_current_user)
    """
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer ") :]
    elif token_admin:
        token = token_admin
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token não informado")

    try:
        payload = verificar_token(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    # Itens 1.1/1.2: token de outro sistema (vendedor) não autentica no
    # administrativo — claim "tipo" + subject prefixado "adm:".
    sub = str(payload.get("sub", ""))
    if payload.get("tipo") != "admin" or not sub.startswith(PREFIXO_SUB_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido para o sistema administrativo",
        )

    usuario = db.get(Usuario, int(sub[len(PREFIXO_SUB_ADMIN) :]))
    if not usuario or not usuario.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido ou inativo")

    return usuario


def require_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    """Dependency FastAPI: exige is_admin=True. Uso: Depends(require_admin)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ação restrita a administradores")
    return current_user


def require_permission(modulo: str, acao: str):
    """Fábrica de dependency FastAPI para checagem de permissão granular.

    FastAPI resolve dependências via `Depends`, não via decorator puro —
    por isso o uso é:

        @router.post("/", dependencies=[Depends(require_permission("pedidos_venda", "criar"))])
        def criar_pedido(...): ...

    ou, quando o usuário autenticado é necessário dentro da função:

        def criar_pedido(usuario: Usuario = Depends(require_permission("pedidos_venda", "criar"))):
            ...

    Administradores (is_admin=True) sempre passam. Para os demais, exige
    uma linha em Permissao com usuario_id + modulo + acao + permitido=True.
    """
    if modulo not in MODULOS_VALIDOS:
        raise ValueError(f"Módulo de permissão inválido: {modulo!r}")
    if acao not in ACOES_VALIDAS:
        raise ValueError(f"Ação de permissão inválida: {acao!r}")

    def checker(
        current_user: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Usuario:
        if current_user.is_admin:
            return current_user

        tem_permissao = (
            db.query(Permissao)
            .filter(
                Permissao.usuario_id == current_user.id,
                Permissao.modulo == modulo,
                Permissao.acao == acao,
                Permissao.permitido == True,  # noqa: E712 — expressão SQL (não comparação Python)
            )
            .first()
        )
        if not tem_permissao:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Você não tem permissão para '{acao}' em '{modulo}'.",
            )
        return current_user

    return checker
