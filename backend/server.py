"""Entry point para PyInstaller.

Em modo frozen, importamos o app diretamente (não como string) para que
o PyInstaller inclua o módulo 'main' e o uvicorn consiga inicializar.
"""

import os
import sys

if getattr(sys, "frozen", False):
    # cwd = pasta de dados do usuário (SMARTCUT_DADOS_DIR, injetada pelo
    # Electron), nunca a pasta de instalação: os arquivos do usuário são
    # resolvidos por services/pasta_dados.py e este chdir é só a rede de
    # segurança para algum caminho relativo esquecido — uma reinstalação apaga
    # a pasta do executável.
    _dados = os.environ.get("SMARTCUT_DADOS_DIR", "").strip()
    if _dados:
        os.makedirs(_dados, exist_ok=True)
    os.chdir(_dados or os.path.dirname(sys.executable))
    # Saída em pipe (Electron) usaria a página de código do Windows (cp1252) e
    # o Electron lê UTF-8: acentos do log — e da mensagem "[boot] …" mostrada
    # no diálogo de erro — chegavam quebrados. O exe ignora PYTHONIOENCODING.
    for _fluxo in (sys.stdout, sys.stderr):
        if _fluxo is not None and hasattr(_fluxo, "reconfigure"):
            _fluxo.reconfigure(encoding="utf-8", errors="replace")

# Importação direta garante que PyInstaller bundle 'main' corretamente
from main import app  # noqa: E402

if __name__ == "__main__":
    import uvicorn

    # log_config=None: o logging é configurado pelo app (logging_conf, item 9.2
    # — formato estruturado + request_id). Sem isso o uvicorn reaplicaria o
    # dictConfig padrão após a importação e quebraria o formato único.
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False, log_level="info", log_config=None)
