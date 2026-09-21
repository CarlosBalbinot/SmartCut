from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    tipo_registro: Mapped[str] = mapped_column(String(20), nullable=False, default="cliente")
    tipo_pessoa: Mapped[str | None] = mapped_column(String(10), nullable=True)
    razao_social: Mapped[str] = mapped_column(String, nullable=False)
    nome_fantasia: Mapped[str | None] = mapped_column(String, nullable=True)
    cnpj: Mapped[str | None] = mapped_column(String(18), nullable=True)
    cpf: Mapped[str | None] = mapped_column(String(14), nullable=True)
    ie: Mapped[str | None] = mapped_column(String, nullable=True)
    inscricao_municipal: Mapped[str | None] = mapped_column(String, nullable=True)
    rg: Mapped[str | None] = mapped_column(String, nullable=True)
    id_estrangeiro: Mapped[str | None] = mapped_column(String, nullable=True)
    tipo_fiscal: Mapped[str | None] = mapped_column(String(20), nullable=True, default="consumidor_final")
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    email_nfe: Mapped[str | None] = mapped_column(String, nullable=True)
    telefone: Mapped[str | None] = mapped_column(String, nullable=True)
    telefone2: Mapped[str | None] = mapped_column(String, nullable=True)
    celular: Mapped[str | None] = mapped_column(String, nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String, nullable=True)
    fax: Mapped[str | None] = mapped_column(String, nullable=True)
    contato: Mapped[str | None] = mapped_column(String, nullable=True)
    endereco: Mapped[str | None] = mapped_column(String, nullable=True)
    numero: Mapped[str | None] = mapped_column(String, nullable=True)
    complemento: Mapped[str | None] = mapped_column(String, nullable=True)
    bairro: Mapped[str | None] = mapped_column(String, nullable=True)
    cidade: Mapped[str | None] = mapped_column(String, nullable=True)
    estado: Mapped[str | None] = mapped_column(String(2), nullable=True)
    cep: Mapped[str | None] = mapped_column(String(9), nullable=True)
    pais: Mapped[str | None] = mapped_column(String, nullable=True)
    codigo_ibge_municipio: Mapped[str | None] = mapped_column(String(7), nullable=True)
    codigo_pais: Mapped[str | None] = mapped_column(String(10), nullable=True, default="1058")
    caixa_postal: Mapped[str | None] = mapped_column(String, nullable=True)
    atividade: Mapped[str | None] = mapped_column(String, nullable=True)
    nascimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    homepage: Mapped[str | None] = mapped_column(String, nullable=True)
    instagram: Mapped[str | None] = mapped_column(String, nullable=True)
    grupo: Mapped[str | None] = mapped_column(String, nullable=True)
    situacao: Mapped[str] = mapped_column(String(10), nullable=False, default="ativo")
    observacoes: Mapped[str | None] = mapped_column(String, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
