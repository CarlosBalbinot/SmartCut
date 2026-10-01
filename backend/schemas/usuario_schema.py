from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PermissaoItem(BaseModel):
    modulo: str
    acao: str


class UsuarioCreate(BaseModel):
    username: str
    nome_completo: str
    senha: str
    permissoes: list[PermissaoItem] = []


class UsuarioUpdate(BaseModel):
    nome_completo: Optional[str] = None
    senha: Optional[str] = None
    ativo: Optional[bool] = None


class UsuarioSelfUpdate(BaseModel):
    nome_completo: Optional[str] = None
    username: Optional[str] = None
    senha_atual: Optional[str] = None
    senha_nova: Optional[str] = None


class PermissoesReplace(BaseModel):
    permissoes: list[PermissaoItem]


class UsuarioResponse(BaseModel):
    id: int
    username: str
    nome_completo: str
    is_admin: bool
    ativo: bool
    criado_em: datetime
    ultimo_acesso: Optional[datetime] = None

    model_config = {"from_attributes": True}
