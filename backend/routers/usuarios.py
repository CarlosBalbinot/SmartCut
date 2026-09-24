from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_admin
from models.usuario import ACOES_VALIDAS, MODULOS_VALIDOS, Permissao, Usuario
from schemas.usuario_schema import (
    PermissoesReplace,
    UsuarioCreate,
    UsuarioResponse,
    UsuarioUpdate,
)
from services import usuario_service
from services.auth_service import validar_politica_senha

router = APIRouter(
    prefix="/api/v1/usuarios",
    tags=["usuarios"],
    dependencies=[Depends(require_admin)],
)


def _validar_permissoes(permissoes: list) -> None:
    for p in permissoes:
        if p.modulo not in MODULOS_VALIDOS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Módulo inválido: {p.modulo}")
        if p.acao not in ACOES_VALIDAS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ação inválida: {p.acao}")


def _detalhe(db: Session, usuario: Usuario) -> dict:
    return {
        **UsuarioResponse.model_validate(usuario).model_dump(),
        "permissoes": usuario_service.listar_permissoes(db, usuario.id),
    }


@router.get("/", response_model=dict)
def listar_usuarios(db: Session = Depends(get_db)):
    usuarios = db.query(Usuario).order_by(Usuario.username).all()
    return {"data": [UsuarioResponse.model_validate(u) for u in usuarios], "error": None}


@router.get("/{usuario_id}", response_model=dict)
def obter_usuario(usuario_id: int, db: Session = Depends(get_db)):
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return {"data": _detalhe(db, usuario), "error": None}


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def criar_usuario(payload: UsuarioCreate, db: Session = Depends(get_db)):
    _validar_permissoes(payload.permissoes)

    # Item 1.3: política mínima de senha.
    msg = validar_politica_senha(payload.senha)
    if msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    usuario = Usuario(
        username=payload.username,
        nome_completo=payload.nome_completo,
        senha_hash=usuario_service.hash_senha(payload.senha),
    )
    db.add(usuario)
    try:
        db.flush()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username já está em uso.")

    for p in payload.permissoes:
        db.add(Permissao(usuario_id=usuario.id, modulo=p.modulo, acao=p.acao, permitido=True))

    db.commit()
    db.refresh(usuario)
    return {"data": _detalhe(db, usuario), "error": None}


@router.put("/{usuario_id}", response_model=dict)
def atualizar_usuario(usuario_id: int, payload: UsuarioUpdate, db: Session = Depends(get_db)):
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    dados = payload.model_dump(exclude_unset=True)
    senha = dados.pop("senha", None)
    if senha:
        # Item 1.3: política mínima de senha.
        msg = validar_politica_senha(senha)
        if msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
        usuario.senha_hash = usuario_service.hash_senha(senha)
    for campo, valor in dados.items():
        setattr(usuario, campo, valor)

    db.commit()
    db.refresh(usuario)
    return {"data": _detalhe(db, usuario), "error": None}


@router.put("/{usuario_id}/permissoes", response_model=dict)
def substituir_permissoes(usuario_id: int, payload: PermissoesReplace, db: Session = Depends(get_db)):
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    _validar_permissoes(payload.permissoes)

    db.query(Permissao).filter(Permissao.usuario_id == usuario_id).delete()
    for p in payload.permissoes:
        db.add(Permissao(usuario_id=usuario_id, modulo=p.modulo, acao=p.acao, permitido=True))

    db.commit()
    return {"data": _detalhe(db, usuario), "error": None}


@router.delete("/{usuario_id}", response_model=dict)
def desativar_usuario(usuario_id: int, db: Session = Depends(get_db)):
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    usuario.ativo = False
    db.commit()
    return {"data": {"desativado": True}, "error": None}
