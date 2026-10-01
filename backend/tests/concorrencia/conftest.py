"""Fixtures dos testes de concorrência (F0, passo 0).

Os testes comuns usam SQLite em memória com StaticPool — uma conexão só,
sem concorrência de verdade. Aqui o banco é um **arquivo** temporário e o
engine sai de `database.criar_engine`, a mesma função do app: cada sessão
tem a sua conexão e as gravações disputam o banco como no aplicativo.

Cada teste roda no SQLite e, quando `SMARTCUT_TEST_PG_URL` estiver
definida, também no PostgreSQL (parâmetro marcado com
`@pytest.mark.postgres`; sem a variável ele é pulado). A URL deve apontar
para um banco descartável: as tabelas são apagadas e recriadas a cada teste.
O PostgreSQL fica para depois da F5 (ver docs/ARQUITETURA.md).
"""

import os

import pytest
from sqlalchemy.orm import sessionmaker

from database import Base, criar_engine

PG_URL_ENV = "SMARTCUT_TEST_PG_URL"


@pytest.fixture(params=["sqlite", pytest.param("postgres", marks=pytest.mark.postgres)])
def engine_concorrente(request, tmp_path):
    if request.param == "postgres":
        url = os.environ.get(PG_URL_ENV, "").strip()
        if not url:
            pytest.skip(f"{PG_URL_ENV} não definida (PostgreSQL fica para depois da F5)")
        eng = criar_engine(url)
        Base.metadata.drop_all(eng)
    else:
        eng = criar_engine(f"sqlite:///{(tmp_path / 'concorrencia.db').as_posix()}")
    Base.metadata.create_all(eng)
    yield eng
    if request.param == "postgres":
        Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def fabrica_sessao(engine_concorrente):
    """Fábrica de sessões com a configuração do app (database.SessionLocal)."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine_concorrente)
