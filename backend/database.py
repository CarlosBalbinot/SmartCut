from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings

engine = create_engine(settings.database_url, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


import models.venda  # noqa: E402,F401  — ensure new tables are in Base.metadata for alembic
import models.pedido  # noqa: E402,F401
import models.encaixe  # noqa: E402,F401
import models.painel_vendedor  # noqa: E402,F401
import models.financeiro  # noqa: E402,F401
