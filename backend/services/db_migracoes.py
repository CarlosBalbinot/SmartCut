"""Migrações de schema via Alembic (itens 5.2 e 5.3 do PROMPT-CORRECOES).

Antes, o schema do banco era criado por `Base.metadata.create_all` no boot
(que cria tabelas novas mas NUNCA altera tabelas existentes — qualquer
evolução ficava invisível/impossível de aplicar em instalações existentes).
A partir daqui o schema é governado por migrações Alembic versionadas e
commitadas no git (baseline + migrações futuras).

Caminhos tratados no boot:

  - Banco novo (sem nenhuma tabela):                      alembic upgrade head
  - Banco da era do create_all (tabelas, sem version):    stamp head + upgrade
  - Banco com alembic_version FORA da cadeia atual
      (ex.: stamp antigo o0d1e2... da cadeia legada):     stamp head + upgrade
  - Banco já sob a cadeia atual:                          alembic upgrade head

O `alembic_version` fica registrado nos casos em que é possível; a partir
daí evolução futura chega por migração e é aplicada nas duas famílias de
banco do projeto: SQLite (desktop) e Postgres (Docker dev/prod).
"""
import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from database import resolver_url

logger = logging.getLogger("uvicorn.error")


def _diretorio_app() -> Path:
    """Raiz do código do backend: diretório do pacote (dev) ou a pasta
    extraída pelo PyInstaller no app empacotado (_MEIPASS)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parent.parent


def _config_alembic() -> Config:
    raiz = _diretorio_app()
    ini = raiz / "alembic.ini"
    script_loc = raiz / "alembic"
    if not ini.exists() or not script_loc.exists():
        raise RuntimeError(
            "Arquivos do Alembic (alembic.ini/alembic/) não encontrados junto ao backend."
        )
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(script_loc))
    return cfg


def _revisoes_conhecidas(cfg: Config) -> set[str]:
    return {s.revision for s in ScriptDirectory.from_config(cfg).walk_revisions()}


def _avisar_drift(engine, url: str) -> None:
    """Log de advertência (não bloqueia o boot): compara o banco existente
    (já fora da era do create_all) com os models atuais. Se houver diferença,
    o operador deve criar uma migração de sincronização."""
    try:
        import models  # noqa: F401, E402 — garante Base.metadata completo
        from alembic.autogenerate import compare_metadata
        from alembic.migration import MigrationContext

        from database import Base

        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        if diff:
            logger.warning(
                "Drift detectado no banco existente (%s): %d diferença(s) em "
                "relação aos models — avalie criar migração de sincronização "
                "(alembic revision --autogenerate).",
                url.split("://", 1)[0],
                len(diff),
            )
    except Exception as err:  # noqa: BLE001 — aviso nunca impede o boot
        logger.warning("Não foi possível checar drift no banco existente: %s", err)


def aplicar_migracoes() -> None:
    """Aplica as migrações Alembic no banco ativo (resolve SMARTCUT_DB_PATH
    para o desktop e DATABASE_URL para Docker/dev — mesma lógica do runtime,
    ver database.resolver_url). Falha alto com mensagem clara: o app nunca
    deve rodar sobre um schema que não é o esperado."""
    url = resolver_url()
    logger.info("Aplicando migrações Alembic (%s)…", url.split("://", 1)[0])

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            tabelas = set(inspect(conn).get_table_names())
            if "alembic_version" in tabelas:
                reg = [r[0] for r in conn.execute(text("select version_num from alembic_version"))]
            else:
                reg = []
    finally:
        engine.dispose()

    cfg = _config_alembic()
    conhecidas = _revisoes_conhecidas(cfg)
    tem_tabelas_app = any(t != "alembic_version" for t in tabelas)
    versao_na_cadeia = bool(reg) and all(rv in conhecidas for rv in reg)

    # Banco existente que não está registrado na cadeia atual (criado pela
    # era do create_all ou com stamp da cadeia legada): o schema já é a
    # baseline — registra head SEM reexecutar a DDL inicial.
    if tem_tabelas_app and (not reg or not versao_na_cadeia):
        logger.info(
            "Banco existente fora da cadeia Alembic atual — registrando "
            "baseline (stamp head) sem reexecutar a DDL inicial."
        )
        # Stamp explícito pelo id do head: `stamp "head"` tentaria calcular o
        # caminho a partir da revisão atual (que pode ser desconhecida — stamp
        # da cadeia legada) e falharia com ResolutionError.
        cabeca = ScriptDirectory.from_config(cfg).get_current_head()
        if not cabeca:
            raise RuntimeError("Nenhuma revisão head encontrada nas migrações Alembic.")
        # purge=True: ignora a revisão atual do banco (pode ser desconhecida —
        # stamp da cadeia legada), apaga o version antigo e grava a baseline.
        command.stamp(cfg, cabeca, purge=True)
        _avisar_drift(engine, url)

    command.upgrade(cfg, "head")
    logger.info("Migrações Alembic aplicadas com sucesso.")