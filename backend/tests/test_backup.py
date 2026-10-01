"""Backup automático do SQLite: rotação pelos N mais recentes e nada de
backup no boot com `uvicorn --reload`."""

import os
import sqlite3
import sys

from scripts import backup_sqlite
from services import backup_service


def _banco(tmp_path):
    db = tmp_path / "smartcut.db"
    con = sqlite3.connect(db)
    con.execute("create table t (x)")
    con.commit()
    con.close()
    return str(db)


def _backup_falso(pasta, ts, aux=False):
    base = pasta / f"smartcut_{ts}"
    base.write_bytes(b"x")
    if aux:
        (pasta / f"smartcut_{ts}-wal").write_bytes(b"x")
    return base


def test_rotacao_mantem_os_mais_recentes(tmp_path):
    pasta = tmp_path / "backups"
    pasta.mkdir()
    antigos = [_backup_falso(pasta, f"20260901_0000{i:02d}", aux=True) for i in range(5)]
    (pasta / "outro_arquivo.txt").write_text("não é backup")

    destino = backup_sqlite.fazer_backup(_banco(tmp_path), str(pasta), manter=3)

    restantes = sorted(p for p in os.listdir(pasta) if not p.endswith(("-wal", "-shm", ".txt")))
    assert len(restantes) == 3
    assert os.path.basename(destino) in restantes  # o novo nunca é apagado
    # Ficam os dois mais recentes dos antigos; o -wal some junto com o principal.
    assert restantes[:2] == [antigos[3].name, antigos[4].name]
    assert not (pasta / f"{antigos[0].name}-wal").exists()
    assert (pasta / f"{antigos[4].name}-wal").exists()
    assert (pasta / "outro_arquivo.txt").exists()


def test_rotacao_abaixo_do_limite_nao_apaga(tmp_path):
    pasta = tmp_path / "backups"
    pasta.mkdir()
    _backup_falso(pasta, "20260901_000000")
    assert backup_sqlite.limpar_backups_antigos(str(pasta), 30) == 0
    assert backup_sqlite.limpar_backups_antigos(str(pasta), 0) == 0
    assert len(os.listdir(pasta)) == 1


def test_sem_backup_no_boot_com_reload(tmp_path, monkeypatch):
    chamadas = []
    monkeypatch.setattr(backup_service, "executar_backup", lambda **kw: chamadas.append(kw))

    monkeypatch.setattr(sys, "argv", ["uvicorn", "main:app", "--reload"])
    assert backup_service.em_reload()
    ag = backup_service.AgendadorBackup("sqlite:///x.db", 3600, backup_no_boot=False)
    ag.iniciar()
    ag._thread.join(0.3)
    ag.parar()
    assert chamadas == []

    monkeypatch.setattr(sys, "argv", ["uvicorn", "main:app"])
    assert not backup_service.em_reload()
    ag = backup_service.AgendadorBackup("sqlite:///x.db", 3600, backup_no_boot=True)
    ag.iniciar()
    ag._thread.join(0.3)
    ag.parar()
    assert len(chamadas) == 1
