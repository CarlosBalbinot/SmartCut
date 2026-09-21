from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.painel_vendedor import Usuario
from models.venda import Vendedor
from services.auth_service import criar_token, verificar_senha

router = APIRouter(prefix="/api/v1/vendedor", tags=["auth"])


class LoginInput(BaseModel):
    username: str
    senha: str


@router.post("/login")
def login(body: LoginInput, db: Session = Depends(get_db)):
    usuario = (
        db.query(Usuario)
        .filter(Usuario.username == body.username, Usuario.ativo == True)
        .first()
    )

    if not usuario or not verificar_senha(body.senha, usuario.senha_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    usuario.ultimo_login = datetime.now(timezone.utc)
    db.commit()

    vendedor = db.get(Vendedor, usuario.vendedor_id)

    token = criar_token(str(usuario.vendedor_id), usuario.username)
    return {
        "data": {
            "token": token,
            "vendedor_id": str(usuario.vendedor_id),
            "nome": vendedor.nome,
            "nome": vendedor.nome if vendedor else usuario.username,
    },
    "error": None
}


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
def setup(body: SetupInput, db: Session = Depends(get_db)):
    if db.query(UsuarioSistema).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Já existe um usuário cadastrado — o setup inicial só pode ser executado uma vez.",
        )

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
    return {"data": {"token": token, "usuario": usuario_service.usuario_para_dict(db, usuario)}, "error": None}


@router_admin.post("/login")
def login_admin(body: LoginAdminInput, db: Session = Depends(get_db)):
    usuario = (
        db.query(UsuarioSistema)
        .filter(UsuarioSistema.username == body.username, UsuarioSistema.ativo == True)
        .first()
    )
    if not usuario or not usuario_service.verificar_senha(body.senha, usuario.senha_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    usuario.ultimo_acesso = datetime.now(timezone.utc)
    db.commit()

    token = usuario_service.criar_token(usuario)
    return {"data": {"token": token, "usuario": usuario_service.usuario_para_dict(db, usuario)}, "error": None}


@router_admin.post("/logout")
def logout_admin():
    # Stateless: o token simplesmente deixa de ser enviado pelo cliente.
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
