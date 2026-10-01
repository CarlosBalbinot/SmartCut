"""Trava de segurança do Alembic (F0): banco alvo resolvido na hora, impresso
no início, e downgrade só com SMARTCUT_PERMITIR_DOWNGRADE=1.

Reproduz o incidente do passo 1a: SMARTCUT_DB_PATH definida DEPOIS da
importação dos settings fazia o comando cair no banco de desenvolvimento.
Aqui o "banco de desenvolvimento" é um arquivo temporário (settings
apontando para ele); o banco real nunca é tocado.
"""

import hashlib
import sqlite3

import pytest
from alembic import command

import database
from services.db_migracoes import PERMITIR_DOWNGRADE, DowngradeBloqueado, _config_alembic, aplicar_migracoes

ANTERIOR = "d5f1b3a7c9e2"  # revisão antes de sequencias (b2e8d4f6a1c3)


def _versao(caminho) -> list[str]:
    with sqlite3.connect(caminho) as c:
        return [r[0] for r in c.execute("select version_num from alembic_version")]


def _tem_tabela(caminho, nome) -> bool:
    with sqlite3.connect(caminho) as c:
        return c.execute("select 1 from sqlite_master where type='table' and name=?", (nome,)).fetchone() is not None


def _hash(caminho) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


@pytest.fixture()
def bancos(tmp_path, monkeypatch):
    """`dev`: banco de desenvolvimento (o que os settings apontam), na head.
    `copia`: cópia dele, alvo dos comandos. Nenhuma variável de ambiente de
    banco definida no começo — como num terminal recém-aberto."""
    dev = tmp_path / "dev.db"
    aplicar_migracoes(f"sqlite:///{dev.as_posix()}")
    copia = tmp_path / "copia.db"
    copia.write_bytes(dev.read_bytes())

    monkeypatch.delenv("SMARTCUT_DB_PATH", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv(PERMITIR_DOWNGRADE, raising=False)
    monkeypatch.setattr(database.settings, "smartcut_db_path", "")
    monkeypatch.setattr(database.settings, "database_url", f"sqlite:///{dev.as_posix()}")
    return dev, copia


def test_variavel_definida_depois_da_importacao_vale(bancos, monkeypatch, capsys):
    dev, copia = bancos
    antes = _hash(dev)
    # Definida agora, com os settings já importados (o caso do incidente).
    monkeypatch.setenv("SMARTCUT_DB_PATH", str(copia))
    monkeypatch.setenv(PERMITIR_DOWNGRADE, "1")

    cfg = _config_alembic()
    command.downgrade(cfg, ANTERIOR)

    assert _versao(copia) == [ANTERIOR]
    assert not _tem_tabela(copia, "sequencias")
    assert _hash(dev) == antes  # o banco de desenvolvimento não foi tocado
    assert f"[alembic] banco alvo: {copia.resolve()}" in capsys.readouterr().err

    command.upgrade(cfg, "head")
    assert _tem_tabela(copia, "sequencias")
    assert _hash(dev) == antes


def test_downgrade_sem_confirmacao_para_mostrando_o_banco(bancos, monkeypatch):
    dev, copia = bancos
    monkeypatch.setenv("SMARTCUT_DB_PATH", str(copia))
    antes = _hash(copia)

    with pytest.raises(DowngradeBloqueado) as exc:
        command.downgrade(_config_alembic(), ANTERIOR)

    assert str(copia.resolve()) in str(exc.value)
    assert PERMITIR_DOWNGRADE in str(exc.value)
    # Parou antes do primeiro passo: nada mudou.
    assert _hash(copia) == antes
    assert _tem_tabela(copia, "sequencias")


def test_stamp_para_tras_tambem_precisa_de_confirmacao(bancos, monkeypatch):
    dev, copia = bancos
    monkeypatch.setenv("SMARTCUT_DB_PATH", str(copia))
    with pytest.raises(DowngradeBloqueado):
        command.stamp(_config_alembic(), ANTERIOR)
    assert _versao(copia) != [ANTERIOR]


def test_url_banco_explicita_tem_prioridade(bancos, monkeypatch):
    dev, copia = bancos
    outro = dev.parent / "outro.db"
    outro.write_bytes(copia.read_bytes())
    monkeypatch.setenv("SMARTCUT_DB_PATH", str(copia))
    monkeypatch.setenv(PERMITIR_DOWNGRADE, "1")

    cfg = _config_alembic()
    cfg.attributes["url_banco"] = f"sqlite:///{outro.as_posix()}"
    command.downgrade(cfg, ANTERIOR)

    assert _versao(outro) == [ANTERIOR]
    assert _tem_tabela(copia, "sequencias")


def test_upgrade_nao_precisa_de_confirmacao(bancos, monkeypatch):
    dev, copia = bancos
    monkeypatch.setenv("SMARTCUT_DB_PATH", str(copia))
    monkeypatch.setenv(PERMITIR_DOWNGRADE, "1")
    command.downgrade(_config_alembic(), ANTERIOR)
    monkeypatch.delenv(PERMITIR_DOWNGRADE)

    command.upgrade(_config_alembic(), "head")
    assert _tem_tabela(copia, "sequencias")
