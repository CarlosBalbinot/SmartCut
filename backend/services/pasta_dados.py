"""Pasta base dos arquivos do usuário (anexos, logo, NF-e, moldes, catálogos,
certificados).

Uma única pasta, fora da pasta de instalação:
  - app instalado: ``SMARTCUT_DADOS_DIR`` injetada pelo Electron
    (``%APPDATA%\\smartcut`` — a mesma do banco e dos modelos de relatório);
  - desenvolvimento / Docker: a pasta ``backend/`` (como sempre foi).

O banco guarda caminhos RELATIVOS a esta pasta (``uploads/financeiro/...``),
com ``/``. Caminhos absolutos antigos continuam sendo lidos como estão.
Nunca usar caminho relativo ao cwd: o executável roda dentro da pasta de
instalação, que uma reinstalação apaga.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

_aviso_dado = False


def pasta_dados() -> Path:
    """Pasta base dos arquivos do usuário (absoluta)."""
    global _aviso_dado
    if settings.smartcut_dados_dir.strip():
        return Path(settings.smartcut_dados_dir.strip()).resolve()
    if getattr(sys, "frozen", False):
        # Executável sem o Electron: nunca a pasta do exe (instalação).
        appdata = os.environ.get("APPDATA", "").strip()
        base = Path(appdata) / "smartcut" if appdata else Path(sys.executable).resolve().parent
        if not _aviso_dado:
            _aviso_dado = True
            logger.warning("SMARTCUT_DADOS_DIR não definido — usando %s para os arquivos do usuário", base)
        return base.resolve()
    # backend/services/pasta_dados.py -> backend/
    return Path(__file__).resolve().parents[1]


def pasta_uploads(*partes: str) -> Path:
    """``<pasta de dados>/uploads[/partes...]``, criada se não existir."""
    pasta = pasta_dados().joinpath("uploads", *partes)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def resolver(caminho: str | os.PathLike | None) -> Path | None:
    """Caminho gravado no banco -> arquivo no disco (None se vazio).

    Relativo (``uploads/...``, inclusive com ``\\`` de gravações antigas) é
    resolvido a partir da pasta de dados; absoluto é devolvido como está.
    """
    if caminho is None or not str(caminho).strip():
        return None
    p = Path(str(caminho).replace("\\", "/"))
    return p if p.is_absolute() else pasta_dados() / p


def existe(caminho: str | os.PathLike | None) -> bool:
    alvo = resolver(caminho)
    return alvo is not None and alvo.is_file()


def relativo(caminho: str | os.PathLike) -> str:
    """Caminho para gravar no banco: relativo à pasta de dados (com ``/``)
    quando está dentro dela; senão absoluto."""
    alvo = resolver(caminho)
    try:
        return alvo.resolve().relative_to(pasta_dados()).as_posix()
    except ValueError:
        return str(alvo.resolve())


def pasta_certificados() -> Path:
    """Pasta dos certificados digitais (.pfx).

    ``CERTIFICADO_DIR`` (o Electron injeta ``<userData>/Certificados``) >
    ``<pasta de dados>/Certificados`` no executável ou com
    ``SMARTCUT_DADOS_DIR`` > ``Certificados/`` na raiz do repositório
    (desenvolvimento, convenção do projeto).
    """
    if settings.certificado_dir.strip():
        return Path(settings.certificado_dir.strip()).resolve()
    if settings.smartcut_dados_dir.strip() or getattr(sys, "frozen", False):
        return pasta_dados() / "Certificados"
    return Path(__file__).resolve().parents[2] / "Certificados"
