"""Entry point para PyInstaller.

Em modo frozen, importamos o app diretamente (não como string) para que
o PyInstaller inclua o módulo 'main' e o uvicorn consiga inicializar.
"""
import os
import sys

if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

# Importação direta garante que PyInstaller bundle 'main' corretamente
from main import app  # noqa: E402

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False, log_level="info")
