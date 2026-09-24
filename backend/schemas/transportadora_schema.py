from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

# Campos de texto livre convertidos para maiúsculo antes de salvar — segunda
# garantia além do uppercase já aplicado no onChange do frontend.
_CAMPOS_UPPER = (
    "nome",
    "nome_fantasia",
    "endereco",
    "numero",
    "complemento",
    "bairro",
    "municipio",
    "contato",
    "placa",
)


class TransportadoraCreate(BaseModel):
    tipo_pessoa: Optional[str] = None
    nome: str
    nome_fantasia: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    placa: Optional[str] = None
    telefone: Optional[str] = None
    fax: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    rg_ie: Optional[str] = None
    email: Optional[str] = None
    email_nfe: Optional[str] = None
    homepage: Optional[str] = None
    contato: Optional[str] = None
    bloqueado: bool = False

    @field_validator(*_CAMPOS_UPPER, mode="before")
    @classmethod
    def to_upper(cls, v):
        return v.upper() if isinstance(v, str) else v


class TransportadoraUpdate(BaseModel):
    tipo_pessoa: Optional[str] = None
    nome: Optional[str] = None
    nome_fantasia: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    placa: Optional[str] = None
    telefone: Optional[str] = None
    fax: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    rg_ie: Optional[str] = None
    email: Optional[str] = None
    email_nfe: Optional[str] = None
    homepage: Optional[str] = None
    contato: Optional[str] = None
    bloqueado: Optional[bool] = None

    @field_validator(*_CAMPOS_UPPER, mode="before")
    @classmethod
    def to_upper(cls, v):
        return v.upper() if isinstance(v, str) else v


class TransportadoraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: Optional[str] = None
    tipo_pessoa: Optional[str] = None
    nome: str
    nome_fantasia: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    placa: Optional[str] = None
    telefone: Optional[str] = None
    fax: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    rg_ie: Optional[str] = None
    email: Optional[str] = None
    email_nfe: Optional[str] = None
    homepage: Optional[str] = None
    contato: Optional[str] = None
    data_cadastro: date
    bloqueado: bool
