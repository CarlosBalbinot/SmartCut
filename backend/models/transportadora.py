from datetime import date

from sqlalchemy import Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Transportadora(Base):
    __tablename__ = "transportadoras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    tipo_pessoa: Mapped[str | None] = mapped_column(String(10), nullable=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    nome_fantasia: Mapped[str | None] = mapped_column(String, nullable=True)
    endereco: Mapped[str | None] = mapped_column(String, nullable=True)
    numero: Mapped[str | None] = mapped_column(String, nullable=True)
    complemento: Mapped[str | None] = mapped_column(String, nullable=True)
    bairro: Mapped[str | None] = mapped_column(String, nullable=True)
    municipio: Mapped[str | None] = mapped_column(String, nullable=True)
    estado: Mapped[str | None] = mapped_column(String(2), nullable=True)
    cep: Mapped[str | None] = mapped_column(String(9), nullable=True)
    placa: Mapped[str | None] = mapped_column(String(10), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String, nullable=True)
    fax: Mapped[str | None] = mapped_column(String, nullable=True)
    cpf_cnpj: Mapped[str | None] = mapped_column(String(18), nullable=True)
    rg_ie: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    email_nfe: Mapped[str | None] = mapped_column(String, nullable=True)
    homepage: Mapped[str | None] = mapped_column(String, nullable=True)
    contato: Mapped[str | None] = mapped_column(String, nullable=True)
    data_cadastro: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    bloqueado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
