from sqlalchemy import engine_from_config, pool
from alembic import context

from database import Base, resolver_url
from config import settings

# Importar todos os modelos para que o Alembic os detecte no autogenerate
import models  # noqa: F401

config = context.config
# Item 5.2/5.3: a URL é resolvida pelo MESMO caminho do runtime (desktop:
# SMARTCUT_DB_PATH aponta para userData; Docker/dev: DATABASE_URL/settings).
config.set_main_option("sqlalchemy.url", resolver_url())

# Logging (Parte 9.2): NÃO aplicamos o fileConfig do alembic.ini de propósito —
# ele criaria um handler "generic" duplicado, fora do formato estruturado com
# request_id. O logging já vem configurado pelo app (logging_conf.py) e os
# registros do alembic fluem pelo handler raiz do backend.

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # necessário para SQLite (não suporta ALTER TABLE nativo)
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # necessário para SQLite
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
