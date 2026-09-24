# -*- coding: utf-8 -*-
"""Backup seguro do banco SQLite (item 3.3).

Faz uma cópia consistente do `smartcut.db` (e dos arquivos auxiliares
`-wal`/`-shm`), com checkpoint passivo do WAL antes de copiar, e mantém uma
retenção de N dias na pasta de backup. Funciona mesmo com o aplicativo em uso
(política WAL = leitores não bloqueiam e a cópia reflete o estado mais
recente confirmado).

Uso (uma execução; ideal para agendador/uso manual):

    py -3.12 scripts/backup_sqlite.py --db C:\\...\\smartcut.db \
        --backup-dir C:\\...\\backups --retention-dias 7

Também pode ser importado: `fazer_backup(db_path, backup_dir, retention_dias)`.

Restore: parar o aplicativo, substituir o `smartcut.db` por um backup
(`smartcut_<timestamp>`), remover `smartcut.db-wal`/`smartcut.db-shm` (o SQLite
reconstrói) e abrir o aplicativo. Detalhes no README (seção Backup).
"""

from __future__ import annotations

import argparse
import datetime
import glob
import os
import shutil
import sqlite3
import sys

# Sufixos do SQLite em modo WAL: o estado real pode estar no -wal.
_SUFIXOS = ("", "-wal", "-shm")


def checkpoint_wal(db_path: str) -> None:
    """Checkpoint passivo do WAL: consolida o que der sem bloquear o app.

    Se falhar (ex.: banco ocupado), o backup segue — a cópia inclui o -wal,
    então nada se perde; o checkpoint apenas reduz o tamanho do arquivo extra.
    """
    if not os.path.exists(db_path + "-wal"):
        return
    try:
        # WAL permite conexões concorrentes: abrir em modo normal é seguro e
        # deixa o checkpoint passivo consolidar as páginas com o app rodando.
        con = sqlite3.connect(os.path.abspath(db_path))
        try:
            con.execute("PRAGMA wal_checkpoint(PASSIVE)")
        finally:
            con.close()
    except sqlite3.Error as err:  # pragma: no cover - ambiente de produção
        print(f"[backup] aviso: checkpoint WAL falhou ({err}) — copiando -wal mesmo assim", file=sys.stderr)


def fazer_backup(db_path: str, backup_dir: str, retention_dias: int) -> str | None:
    """Copia o banco (e -wal/-shm) para backup_dir com timestamp e limpa antigos.

    Retorna o caminho base do backup criado (sem sufixo) ou None se o banco
    não existir.
    """
    if not os.path.isfile(db_path):
        print(f"[backup] banco não encontrado: {db_path}", file=sys.stderr)
        return None

    os.makedirs(backup_dir, exist_ok=True)
    checkpoint_wal(db_path)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    destino_base = os.path.join(backup_dir, f"smartcut_{ts}")
    for sufixo in _SUFIXOS:
        origem = db_path + sufixo
        if os.path.exists(origem):
            shutil.copy2(origem, destino_base + sufixo)

    limpar_backups_antigos(backup_dir, retention_dias)
    print(f"[backup] ok: {destino_base}")
    return destino_base


def limpar_backups_antigos(backup_dir: str, retention_dias: int) -> int:
    """Remove backups `smartcut_*` mais velhos que retention_dias. Retorna nº removido."""
    if retention_dias <= 0:
        return 0
    limite = datetime.datetime.now() - datetime.timedelta(days=retention_dias)
    removidos = 0
    for caminho in glob.glob(os.path.join(backup_dir, "smartcut_*")):
        base = os.path.basename(caminho)
        # Ignora sufixos (-wal/-shm): o "alvo" de retenção é o arquivo principal.
        if base.endswith(("-wal", "-shm")):
            continue
        try:
            quando = datetime.datetime.strptime(base, "smartcut_%Y%m%d_%H%M%S")
        except ValueError:
            continue
        if quando < limite:
            try:
                os.remove(caminho)
                # Remove também os auxiliares correspondentes (se existirem).
                for sufixo in ("-wal", "-shm"):
                    aux = caminho + sufixo
                    if os.path.exists(aux):
                        os.remove(aux)
                removidos += 1
            except OSError as err:
                print(f"[backup] aviso: não removeu {caminho} ({err})", file=sys.stderr)
    if removidos:
        print(f"[backup] retenção: removidos {removidos} backup(s) antigo(s)")
    return removidos


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup seguro do SQLite do SmartCut")
    parser.add_argument("--db", required=True, help="Caminho do arquivo .db")
    parser.add_argument("--backup-dir", required=True, help="Pasta onde ficam os backups")
    parser.add_argument("--retention-dias", type=int, default=7, help="Dias de retenção (padrão: 7)")
    args = parser.parse_args()
    resultado = fazer_backup(args.db, args.backup_dir, args.retention_dias)
    if not resultado:
        sys.exit(2)


if __name__ == "__main__":
    main()
