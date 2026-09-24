from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from jwt import InvalidTokenError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.painel_vendedor import Usuario
from models.venda import Vendedor
from services import rate_limit
from services.auth_service import (
    criar_token_vendedor,
    revogar_token,
    validar_politica_senha,
    verificar_senha,
    verificar_token,
)

router = APIRouter(prefix="/api/v1/vendedor", tags=["auth"])


# ── Cookie de sessão (item 1.4) ────────────────────────────────────────────
# Navegador (dev via Vite / implantação web): o token viaja em cookie
# HttpOnly emitido pelo backend — scripts da página não conseguem ler o token.
# No Electron o token fica criptografado via safeStorage (electronAPI) e segue
# o fluxo por header Authorization; o cookie é apenas um fallback inofensivo.
COOKIE_ADMIN = "smartcut_token"
COOKIE_VENDEDOR = "smartcut_vendedor_token"
_TOKENS_MAX_AGE = 8 * 60 * 60  # mesma duração do JWT (8h)


def _definir_cookie_sessao(response: Response, chave: str, valor: str) -> None:
    response.set_cookie(
        key=chave,
        value=valor,
        max_age=_TOKENS_MAX_AGE,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path="/",
    )


def _limpar_cookie_sessao(response: Response, chave: str) -> None:
    response.delete_cookie(key=chave, path="/")


class LoginInput(BaseModel):
    username: str
    senha: str


@router.post("/login")
def login(body: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "desconhecido"

    # Item 1.3: bloqueio temporário após falhas consecutivas (força bruta).
    restante = rate_limit.verificar_bloqueio(body.username, ip)
    if restante:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Muitas tentativas de login. Tente novamente em "
                f"{max(1, int(restante // 60))} minuto(s)."
            ),
        )

    usuario = (
        db.query(Usuario)
        .filter(Usuario.username == body.username, Usuario.ativo == True)
        .first()
    )

    if not usuario or not verificar_senha(body.senha, usuario.senha_hash):
        rate_limit.registrar_falha(body.username, ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    rate_limit.registrar_sucesso(body.username, ip)

    usuario.ultimo_login = datetime.now(timezone.utc)
    db.commit()

    vendedor = db.get(Vendedor, usuario.vendedor_id)

    token = criar_token_vendedor(str(usuario.vendedor_id), usuario.username)
    # Item 1.4: cookie HttpOnly para o painel rodando em navegador.
    _definir_cookie_sessao(response, COOKIE_VENDEDOR, token)
    return {
        "data": {
            "token": token,
            "vendedor_id": str(usuario.vendedor_id),
            "nome": vendedor.nome,
            "nome": vendedor.nome if vendedor else usuario.username,
    },
    "error": None
}


@router.post("/logout")
def logout_vendedor(
    response: Response,
    request: Request,
    authorization: str = Header(default=""),
):
    # Item 1.3/1.4: revoga o jti do token atual e limpa o cookie de sessão.
    token = (
        authorization[7:]
        if authorization.startswith("Bearer ")
        else request.cookies.get(COOKIE_VENDEDOR, "")
    )
    if token:
        try:
            dados = verificar_token(token)
        except InvalidTokenError:
            dados = None  # já expirado/inválido/revogado — nada a revogar
        if dados:
            revogar_token(dados.get("jti", ""))
    _limpar_cookie_sessao(response, COOKIE_VENDEDOR)
    return {"data": {"deslogado": True}, "error": None}


# ═══════════════════════════════════════════════════════════════════════
# Auth do sistema administrativo (SmartCut desktop) — JWT e tabela
# separados do login do painel do vendedor acima.
# ═══════════════════════════════════════════════════════════════════════

from models.usuario import Usuario as UsuarioSistema        # noqa: E402
from middleware.permissions import get_current_user         # noqa: E402
from schemas.usuario_schema import UsuarioSelfUpdate         # noqa: E402
from services import usuario_service                        # noqa: E402

router_admin = APIRouter(prefix="/api/v1/auth", tags=["auth-admin"])


class SetupInput(BaseModel):
    username: str
    nome_completo: str
    senha: str


class LoginAdminInput(BaseModel):
    username: str
    senha: str


@router_admin.get("/primeiro-acesso")
def primeiro_acesso(db: Session = Depends(get_db)):
    existe = db.query(UsuarioSistema).first() is not None
    return {"primeiro_acesso": not existe}


@router_admin.post("/setup", status_code=status.HTTP_201_CREATED)
def setup(body: SetupInput, response: Response, db: Session = Depends(get_db)):
    if db.query(UsuarioSistema).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Já existe um usuário cadastrado — o setup inicial só pode ser executado uma vez.",
        )

    # Item 1.3: política mínima de senha antes de cadastrar.
    msg = validar_politica_senha(body.senha)
    if msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    usuario = UsuarioSistema(
        username=body.username,
        nome_completo=body.nome_completo,
        senha_hash=usuario_service.hash_senha(body.senha),
        is_admin=True,
    )
    db.add(usuario)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username já está em uso.")
    db.refresh(usuario)

    token = usuario_service.criar_token(usuario)
    # Item 1.4: cookie HttpOnly para o navegador (dev/implantacão web).
    _definir_cookie_sessao(response, COOKIE_ADMIN, token)
    return {"data": {"token": token, "usuario": usuario_service.usuario_para_dict(db, usuario)}, "error": None}


@router_admin.post("/login")
def login_admin(body: LoginAdminInput, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "desconhecido"

    # Item 1.3: bloqueio temporário após falhas consecutivas (força bruta).
    restante = rate_limit.verificar_bloqueio(body.username, ip)
    if restante:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Muitas tentativas de login. Tente novamente em "
                f"{max(1, int(restante // 60))} minuto(s)."
            ),
        )

    usuario = (
        db.query(UsuarioSistema)
        .filter(UsuarioSistema.username == body.username, UsuarioSistema.ativo == True)
        .first()
    )
    if not usuario or not usuario_service.verificar_senha(body.senha, usuario.senha_hash):
        rate_limit.registrar_falha(body.username, ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    rate_limit.registrar_sucesso(body.username, ip)

    usuario.ultimo_acesso = datetime.now(timezone.utc)
    db.commit()

    token = usuario_service.criar_token(usuario)
    # Item 1.4: cookie HttpOnly para o navegador (dev/implantacão web).
    _definir_cookie_sessao(response, COOKIE_ADMIN, token)
    return {"data": {"token": token, "usuario": usuario_service.usuario_para_dict(db, usuario)}, "error": None}


@router_admin.post("/logout")
def logout_admin(
    response: Response,
    request: Request,
    authorization: str = Header(default=""),
):
    # Item 1.3: revoga o token atual (jti) — a sessão deixa de valer já.
    token = (
        authorization[7:]
        if authorization.startswith("Bearer ")
        else request.cookies.get(COOKIE_ADMIN, "")
    )
    if token:
        try:
            dados = verificar_token(token)
        except InvalidTokenError:
            dados = None  # token já expirado/inválido/revogado — nada a revogar
        if dados:
            revogar_token(dados.get("jti", ""))
    # Item 1.4: remove o cookie no navegador.
    _limpar_cookie_sessao(response, COOKIE_ADMIN)
    return {"data": {"deslogado": True}, "error": None}


@router_admin.get("/me")
def me(usuario: UsuarioSistema = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"data": usuario_service.usuario_para_dict(db, usuario), "error": None}


@router_admin.patch("/me")
def atualizar_me(
    payload: UsuarioSelfUpdate,
    usuario: UsuarioSistema = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Autoatendimento: o usuário logado edita os próprios dados (nome, login, senha).

    Diferente do PUT /usuarios/{id} (admin-only, sem checagem de senha atual),
    aqui qualquer usuário autenticado pode alterar o próprio cadastro, e a
    troca de senha exige confirmação da senha atual.
    """
    if payload.senha_nova:
        if not payload.senha_atual or not usuario_service.verificar_senha(payload.senha_atual, usuario.senha_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta.")
        # Item 1.3: política mínima de senha na troca.
        msg = validar_politica_senha(payload.senha_nova)
        if msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
        usuario.senha_hash = usuario_service.hash_senha(payload.senha_nova)

    if payload.nome_completo:
        usuario.nome_completo = payload.nome_completo

    if payload.username and payload.username != usuario.username:
        usuario.username = payload.username
        try:
            db.flush()
        except Exception:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username já está em uso.")

    db.commit()
    db.refresh(usuario)
    return {"data": usuario_service.usuario_para_dict(db, usuario), "error": None}
