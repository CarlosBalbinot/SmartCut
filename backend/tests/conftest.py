"""Fixtures comuns da suíte de testes (Parte 8.1).

Banco: SQLite em memória com pool compartilhado (StaticPool), recriado por
teste via ``Base.metadata.create_all`` — não toca no banco real (``smartcut.db``)
nem executa Alembic. O app exposto é o app real com o lifespan desativado
(nada de migrações/backup no boot) e o ``get_db`` sobrescrito para o banco de
teste. Rate-limit é zerado entre testes (estado global em memória).
"""

import sqlalchemy as sa
import pytest
from contextlib import asynccontextmanager
from fastapi.testclient import TestClient
from sqlalchemy import Column, Table, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Importa o app real registrando todos os models no Base.metadata.
import main as main_mod  # noqa: F401

from database import Base, get_db
from models.cliente import Cliente
from models.usuario import Usuario
from services.auth_service import criar_token_admin, hash_senha

SENHA_PADRAO = "senha@123"

# Tabela legada `tecidos`: a coluna `encaixes.tecido_id` (FK legada, sempre
# NULL nos fluxos atuais — a hierarquia nova usa lote_id) ainda referencia
# essa tabela, que não tem mais modelo ORM. Para o create_all dos testes não
# falhar na ordenação das FKs, registra a tabela mínima no metadata — o mesmo
# formato que a migração baseline (f9d6a18fef75) criou no banco real.
if "tecidos" not in Base.metadata.tables:
    Table(
        "tecidos",
        Base.metadata,
        Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    )


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session(engine):
    """Sessão direta para montar dados de apoio (fixtures/ORM)."""
    Session = sessionmaker(bind=engine, expire_on_commit=False, autoflush=True)
    sess = Session()
    yield sess
    sess.close()


@pytest.fixture()
def override_get_db(engine):
    """Dependency override de get_db: sessão isolada apontando para o teste."""
    Session = sessionmaker(bind=engine, expire_on_commit=False, autoflush=True)

    def _get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    return _get_db


@asynccontextmanager
async def _lifespan_noop(app):
    """No-op: o lifespan real do app roda migrações/backup (nunca nos testes)."""
    yield


@pytest.fixture()
def app(override_get_db):
    # Mesma instância do app real, com lifespan substituído por no-op e com o
    # banco de teste (nada de migrações/backup no boot dos testes).
    main_mod.app.router.lifespan_context = _lifespan_noop
    main_mod.app.dependency_overrides[get_db] = override_get_db
    yield main_mod.app
    main_mod.app.dependency_overrides.clear()


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def cliente(db_session):
    """Cliente de teste compartilhado pelos módulos de pedido de venda."""
    c = Cliente(
        codigo="0001",
        tipo_registro="cliente",
        tipo_pessoa="juridica",
        razao_social="CLIENTE LTDA",
        cnpj="12345678000190",
        endereco="RUA A",
        numero="10",
        bairro="CENTRO",
        cidade="CAXIAS DO SUL",
        estado="RS",
        cep="95000000",
        codigo_ibge_municipio="4305108",
    )
    db_session.add(c)
    db_session.commit()
    return c


@pytest.fixture()
def admin(db_session):
    admin = Usuario(
        username="admin",
        nome_completo="Administrador de Teste",
        senha_hash=hash_senha(SENHA_PADRAO),
        is_admin=True,
    )
    db_session.add(admin)
    db_session.commit()
    return admin


@pytest.fixture()
def usuario_simples(db_session):
    u = Usuario(
        username="operador",
        nome_completo="Operador de Teste",
        senha_hash=hash_senha(SENHA_PADRAO),
        is_admin=False,
    )
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture()
def token_admin(admin):
    return criar_token_admin(admin)


@pytest.fixture()
def headers_admin(token_admin):
    return {"Authorization": f"Bearer {token_admin}"}


@pytest.fixture(autouse=True)
def _limpar_estados_globais():
    """Rate-limit é global em memória (services/rate_limit.py) — zera entre
    testes para bloqueios de força bruta não vazarem de um teste para o outro."""
    from services import rate_limit

    rate_limit._FALHAS.clear()
    rate_limit._BLOQUEIO_ATE.clear()
    rate_limit._COOLDOWN_NIVEL.clear()
    yield


@pytest.fixture(autouse=True)
def _pasta_dados_temporaria(tmp_path_factory, monkeypatch):
    """Arquivos do usuário (anexos, logo, NF-e, certificados...) vão para uma
    pasta temporária — nunca para backend/uploads nem Certificados/ reais."""
    from config import settings

    dados = tmp_path_factory.mktemp("dados")
    monkeypatch.setattr(settings, "smartcut_dados_dir", str(dados))
    monkeypatch.setattr(settings, "certificado_dir", "")
    yield dados
