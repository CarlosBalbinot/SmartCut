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
