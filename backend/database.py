from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings


def resolver_url() -> str:
    # Em produção (Electron empacotado), o main.js define SMARTCUT_DB_PATH
    # apontando para o diretório de dados do usuário. Item 10.4: fonte única
    # de configuração — tudo passa pelos settings do pydantic (config.py).
    if settings.smartcut_db_path:
        return f"sqlite:///{settings.smartcut_db_path}"
    return settings.database_url


def criar_engine(url: str):
    """Engine com a configuração do app. Os testes de concorrência
    (tests/concorrencia) usam esta mesma função, para disputar o banco com a
    configuração real.

    `connect_args={"check_same_thread": False}` é específico do SQLite (o
    banco do SmartCut); só é aplicado quando o driver é SQLite."""
    kwargs: dict = {"echo": False}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


_url = resolver_url()
engine = criar_engine(_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


import models.venda  # noqa: E402,F401  — registrar tabelas no Base.metadata
import models.pedido  # noqa: E402,F401
import models.encaixe  # noqa: E402,F401
import models.painel_vendedor  # noqa: E402,F401
import models.financeiro  # noqa: E402,F401
import models.produto  # noqa: E402,F401
import models.transportadora  # noqa: E402,F401
import models.usuario  # noqa: E402,F401
import models.tes  # noqa: E402,F401
import models.nfe  # noqa: E402,F401
import models.condicao_pagamento  # noqa: E402,F401
import models.tabela_grade  # noqa: E402,F401
import models.configuracao_grade  # noqa: E402,F401
import models.produto_sku  # noqa: E402,F401
