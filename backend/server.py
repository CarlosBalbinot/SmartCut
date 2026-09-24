"""Entry point para PyInstaller.

Em modo frozen, importamos o app diretamente (não como string) para que
o PyInstaller inclua o módulo 'main' e o uvicorn consiga inicializar.
"""

import os
import sys

if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

# Importação direta garante que PyInstaller bundle 'main' corretamente
from main import app  # noqa: E402

if __name__ == "__main__":
    import uvicorn

    # log_config=None: o logging é configurado pelo app (logging_conf, item 9.2
    # — formato estruturado + request_id). Sem isso o uvicorn reaplicaria o
    # dictConfig padrão após a importação e quebraria o formato único.
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False, log_level="info", log_config=None)
