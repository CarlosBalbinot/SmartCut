"""Boot das migrações (services/db_migracoes.py): nunca carimbar sem criar a
estrutura. Bancos SQLite em arquivo temporário (tmp_path) — o banco real
não é tocado."""

import sqlite3

import pytest

from services.db_migracoes import MSG_SEM_VERSAO, BancoSemVersao, aplicar_migracoes


def _tabelas(caminho) -> set[str]:
    with sqlite3.connect(caminho) as c:
        return {
            r[0] for r in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")
        }


def _versao(caminho) -> list[str]:
    with sqlite3.connect(caminho) as c:
        return [r[0] for r in c.execute("select version_num from alembic_version")]


def test_banco_vazio_recebe_a_estrutura_completa(tmp_path):
    db = tmp_path / "novo.db"
    aplicar_migracoes(f"sqlite:///{db}")
    tabelas = _tabelas(db) - {"alembic_version"}
    # 48 da baseline (f9d6a18fef75) + 4 criadas depois: ordens_corte,
    # itens_ordem_corte, ordem_corte_tecidos (a3b5c7d9e1f2) e encaixe_camadas
    # (d5f1b3a7c9e2).
    assert len(tabelas) == 52
    assert {"produtos", "usuarios_sistema", "permissoes", "ordens_corte", "encaixe_camadas"} <= tabelas
    with sqlite3.connect(db) as c:
        assert "numero" in {r[1] for r in c.execute("pragma table_info(encaixes)")}
    assert len(_versao(db)) == 1


def test_banco_na_head_nao_muda(tmp_path):
    db = tmp_path / "novo.db"
    aplicar_migracoes(f"sqlite:///{db}")
    antes = _versao(db)
    aplicar_migracoes(f"sqlite:///{db}")
    assert _versao(db) == antes


def test_banco_com_tabelas_sem_versao_para_sem_carimbar(tmp_path):
    db = tmp_path / "antigo.db"
    with sqlite3.connect(db) as c:
        c.execute("create table lancamentos (id text primary key)")
    with pytest.raises(BancoSemVersao, match=MSG_SEM_VERSAO):
        aplicar_migracoes(f"sqlite:///{db}")
    assert _tabelas(db) == {"lancamentos"}  # nada criado, nada carimbado


def test_banco_com_versao_fora_da_cadeia_para(tmp_path):
    db = tmp_path / "legado.db"
    with sqlite3.connect(db) as c:
        c.execute("create table lancamentos (id text primary key)")
        c.execute("create table alembic_version (version_num varchar(32) not null)")
        c.execute("insert into alembic_version values ('o0d1e2f3a4b5')")
    with pytest.raises(BancoSemVersao):
        aplicar_migracoes(f"sqlite:///{db}")
    assert _versao(db) == ["o0d1e2f3a4b5"]
