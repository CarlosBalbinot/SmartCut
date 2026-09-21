from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


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
