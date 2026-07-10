import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings


def _resolve_db_url() -> str:
    # Em produção (Electron empacotado), o main.js define SMARTCUT_DB_PATH
    # apontando para o diretório de dados do usuário.
    db_path = os.environ.get("SMARTCUT_DB_PATH")
    if db_path:
        return f"sqlite:///{db_path}"
    return settings.database_url


engine = create_engine(
    _resolve_db_url(),
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


import models.venda          # noqa: E402,F401  — registrar tabelas no Base.metadata
import models.pedido         # noqa: E402,F401
import models.encaixe        # noqa: E402,F401
import models.painel_vendedor  # noqa: E402,F401
import models.financeiro     # noqa: E402,F401
