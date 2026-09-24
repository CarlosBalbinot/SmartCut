# -*- coding: utf-8 -*-
"""Agendamento do backup automático do SQLite (item 3.3).

Integra o `scripts/backup_sqlite.py` ao ciclo de vida do backend: no startup
(ou imediatamente depois) roda um backup e, depois, repete a cada
`BACKUP_INTERVAL_SEC`. Só tem efeito quando o banco é SQLite — no
Docker/Postgres quem cuida do backup é o serviço `pg_dump` do
`docker-compose.prod.yml`.
"""
from __future__ import annotations

import datetime
import logging
import os
import threading
import time

from sqlalchemy.engine import make_url

from scripts.backup_sqlite import fazer_backup

logger = logging.getLogger("uvicorn.error")


def caminho_banco_sqlite(engine_url: str, db_path_env: str = "") -> str | None:
    """Resolve o caminho do arquivo .db quando o engine é SQLite.

    Prioriza SMARTCUT_DB_PATH (Electron), depois o engine URL resolvido.
    Retorna None para Postgres/outros ou banco em memória.
    """
    if db_path_env:
        return os.path.abspath(db_path_env)

    if not engine_url.startswith("sqlite"):
        return None
    url = make_url(engine_url)
    if url.database in ("", ":memory:"):
        return None
    return os.path.abspath(url.database)


def pasta_backup(db_path: str, backup_dir_config: str) -> str:
    """Pasta de backup: BACKUP_DIR se definido; senão 'backups' ao lado do .db."""
    if backup_dir_config and backup_dir_config.strip():
        return os.path.abspath(backup_dir_config)
    return os.path.join(os.path.dirname(db_path), "backups")


def executar_backup(
    *,
    engine_url: str,
    db_path_env: str = "",
    backup_dir_config: str = "",
    retention_dias: int = 7,
) -> str | None:
    """Executa um backup agora, se aplicável (SQLite). Retorna caminho ou None."""
    db_path = caminho_banco_sqlite(engine_url, db_path_env)
    if not db_path:
        logger.info("[backup] banco não é SQLite — backup local desabilitado (Postgres usa pg_dump no compose)")
        return None
    return fazer_backup(db_path, pasta_backup(db_path, backup_dir_config), retention_dias)


class AgendadorBackup:
    """Roda o backup imediatamente e a cada intervalo em thread daemon."""

    def __init__(self, engine_url: str, intervalo_seg: int, **kwargs) -> None:
        self._engine_url = engine_url
        self._intervalo_seg = max(60, intervalo_seg)
        self._kwargs = kwargs
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None

    def iniciar(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="backup-sqlite", daemon=True)
        self._thread.start()
        logger.info("[backup] agendador iniciado (intervalo=%ss)", self._intervalo_seg)

    def _loop(self) -> None:
        while not self._parar.is_set():
            try:
                executar_backup(engine_url=self._engine_url, **self._kwargs)
            except Exception as err:  # noqa: BLE001 — nunca derruba o servidor
                logger.error("[backup] falha ao executar backup", exc_info=err)
            self._parar.wait(self._intervalo_seg)

    def parar(self) -> None:
        self._parar.set()


_agendador: AgendadorBackup | None = None


def iniciar_backup_automatico() -> None:
    """Chamado no lifespan do FastAPI (startup)."""
    global _agendador
    from config import settings  # import local evita ciclo no import do módulo
    from database import engine

    _agendador = AgendadorBackup(
        engine_url=str(engine.url),
        intervalo_seg=settings.backup_interval_sec,
        db_path_env=os.environ.get("SMARTCUT_DB_PATH", ""),
        backup_dir_config=settings.backup_dir,
        retention_dias=settings.backup_retention_dias,
    )
    _agendador.iniciar()


def parar_backup_automatico() -> None:
    """Chamado no lifespan do FastAPI (shutdown)."""
    global _agendador
    if _agendador:
        _agendador.parar()
        _agendador = None


# Só para conferência em logs: formato legível do próximo backup.
def _proximo_registro() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")