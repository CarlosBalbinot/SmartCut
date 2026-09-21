from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ClienteCreate(BaseModel):
    tipo_registro: str = "cliente"
    tipo_pessoa: Optional[str] = None
    razao_social: str
    nome_fantasia: Optional[str] = None
    cnpj: Optional[str] = None
    cpf: Optional[str] = None
    ie: Optional[str] = None
    inscricao_municipal: Optional[str] = None
    rg: Optional[str] = None
    id_estrangeiro: Optional[str] = None
    tipo_fiscal: Optional[str] = "consumidor_final"
    email: Optional[str] = None
    email_nfe: Optional[str] = None
    telefone: Optional[str] = None
    telefone2: Optional[str] = None
    celular: Optional[str] = None
    whatsapp: Optional[str] = None
    fax: Optional[str] = None
    contato: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    pais: Optional[str] = None
    codigo_ibge_municipio: Optional[str] = None
    codigo_pais: Optional[str] = "1058"
    caixa_postal: Optional[str] = None
    atividade: Optional[str] = None
    nascimento: Optional[date] = None
    homepage: Optional[str] = None
    instagram: Optional[str] = None
    grupo: Optional[str] = None
    situacao: str = "ativo"
    observacoes: Optional[str] = None


class ClienteUpdate(BaseModel):
    tipo_registro: Optional[str] = None
    tipo_pessoa: Optional[str] = None
    razao_social: Optional[str] = None
    nome_fantasia: Optional[str] = None
    cnpj: Optional[str] = None
    cpf: Optional[str] = None
    ie: Optional[str] = None
    inscricao_municipal: Optional[str] = None
    rg: Optional[str] = None
    id_estrangeiro: Optional[str] = None
    tipo_fiscal: Optional[str] = None
    email: Optional[str] = None
    email_nfe: Optional[str] = None
    telefone: Optional[str] = None
    telefone2: Optional[str] = None
    celular: Optional[str] = None
    whatsapp: Optional[str] = None
    fax: Optional[str] = None
    contato: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    pais: Optional[str] = None
    codigo_ibge_municipio: Optional[str] = None
    codigo_pais: Optional[str] = None
    caixa_postal: Optional[str] = None
    atividade: Optional[str] = None
    nascimento: Optional[date] = None
    homepage: Optional[str] = None
    instagram: Optional[str] = None
    grupo: Optional[str] = None
    situacao: Optional[str] = None
    observacoes: Optional[str] = None
    ativo: Optional[bool] = None


class ClienteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: Optional[str] = None
    tipo_registro: str
    tipo_pessoa: Optional[str] = None
    razao_social: str
    nome_fantasia: Optional[str] = None
    cnpj: Optional[str] = None
    cpf: Optional[str] = None
    ie: Optional[str] = None
    inscricao_municipal: Optional[str] = None
    rg: Optional[str] = None
    id_estrangeiro: Optional[str] = None
    tipo_fiscal: Optional[str] = None
    email: Optional[str] = None
    email_nfe: Optional[str] = None
    telefone: Optional[str] = None
    telefone2: Optional[str] = None
    celular: Optional[str] = None
    whatsapp: Optional[str] = None
    fax: Optional[str] = None
    contato: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    pais: Optional[str] = None
    codigo_ibge_municipio: Optional[str] = None
    codigo_pais: Optional[str] = None
    caixa_postal: Optional[str] = None
    atividade: Optional[str] = None
    nascimento: Optional[date] = None
    homepage: Optional[str] = None
    instagram: Optional[str] = None
    grupo: Optional[str] = None
    situacao: str
    observacoes: Optional[str] = None
    ativo: bool
    created_at: datetime
