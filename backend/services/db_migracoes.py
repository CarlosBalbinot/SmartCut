"""Migrações de schema via Alembic (itens 5.2 e 5.3 de docs/historico/PROMPT-CORRECOES.md).

Antes, o schema do banco era criado por `Base.metadata.create_all` no boot
(que cria tabelas novas mas NUNCA altera tabelas existentes — qualquer
evolução ficava invisível/impossível de aplicar em instalações existentes).
A partir daqui o schema é governado por migrações Alembic versionadas e
commitadas no git (baseline + migrações futuras).

Caminhos tratados no boot:

  - Banco novo (sem nenhuma tabela):                      alembic upgrade head
  - Banco já sob a cadeia atual:                          alembic upgrade head
  - Banco com tabelas e SEM alembic_version, ou com
      versão FORA da cadeia atual:                        para com erro
      ("Banco sem versão registrada, contate o suporte")

Não há mais stamp automático: carimbar a head num banco antigo registrava a
versão sem criar a estrutura das migrações puladas. Um banco nessa situação
é montado à parte (scripts/montar_banco_producao.py).
"""

import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from database import resolver_url

logger = logging.getLogger(__name__)


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
        raise RuntimeError("Arquivos do Alembic (alembic.ini/alembic/) não encontrados junto ao backend.")
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(script_loc))
    return cfg


def _revisoes_conhecidas(cfg: Config) -> set[str]:
    return {s.revision for s in ScriptDirectory.from_config(cfg).walk_revisions()}


class BancoSemVersao(RuntimeError):
    """Banco com tabelas mas sem versão Alembic reconhecível: o boot para."""


MSG_SEM_VERSAO = "Banco sem versão registrada, contate o suporte."


def aplicar_migracoes(url: str | None = None) -> None:
    """Aplica as migrações Alembic no banco ativo (resolve SMARTCUT_DB_PATH
    para o desktop e DATABASE_URL em desenvolvimento — mesma lógica do runtime,
    ver database.resolver_url) ou no banco de ``url`` (script de montagem).

    - Banco novo (sem tabelas): upgrade head desde a baseline.
    - Banco registrado na cadeia atual: upgrade head.
    - Banco com tabelas e SEM versão (ou com versão fora da cadeia): para com
      BancoSemVersao. Nunca carimba (stamp) a versão: o stamp registrava a
      head sem criar a estrutura, e o banco ficava sem as tabelas/colunas das
      migrações puladas (caso da instalação de 28/09, carimbada em
      f8a6f7ef2ccf sem 16 das 48 tabelas).
    """
    url = url or resolver_url()
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
    cfg.attributes["url_banco"] = url
    conhecidas = _revisoes_conhecidas(cfg)
    tem_tabelas_app = any(t != "alembic_version" for t in tabelas)

    if tem_tabelas_app and not reg:
        logger.error("[boot] %s O banco tem tabelas mas não tem alembic_version.", MSG_SEM_VERSAO)
        raise BancoSemVersao(MSG_SEM_VERSAO)
    desconhecidas = [rv for rv in reg if rv not in conhecidas]
    if desconhecidas:
        logger.error("[boot] %s Versão fora da cadeia de migrações: %s.", MSG_SEM_VERSAO, ", ".join(desconhecidas))
        raise BancoSemVersao(MSG_SEM_VERSAO)

    command.upgrade(cfg, "head")
    logger.info("Migrações Alembic aplicadas com sucesso.")
