# -*- coding: utf-8 -*-
"""Cifragem em repouso de segredos do certificado digital (item 4.2).

O banco NUNCA guarda a senha do certificado em texto claro nem em base64
reversível: guarda apenas um blob cifrado no formato `enc:v1:<iv>:<tag+data>`
(AES-256-GCM, via `cryptography`). A chave de cifragem nunca fica no banco.

Fontes da chave, em ordem de prioridade:
  1. ``CERT_SENHA_KEY``  (settings/ambiente) — Docker/servidor: chave mestre
     fornecida pelo operador no ambiente (secret manager, .env do compose…).
  2. ``SMARTCUT_CERT_KEY`` (ambiente) — desktop: o Electron gera uma chave por
     instalação, guarda protegida pelo cofre do sistema (DPAPI via
     `safeStorage`) em `userData/smartcut-cert-key.bin` e injeta a chave apenas
     na variável de ambiente do processo do backend.

Sem chave disponível:
  - persistir uma NOVA senha é recusado com mensagem clara (Docker/navegador:
    exija a senha em runtime ou defina a chave mestre — trade-off documentado
    no README);
  - valores legados (base64 reversível gravados antes da correção) continuam
    utilizáveis em leitura e são migrados para o formato cifrado pelo
    `migrar_segredos_legados` assim que houver chave (startup do backend).
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_PREFIXO = "enc:v1:"
_IV_BYTES = 12  # AES-GCM recomenda nonce de 12 bytes


def _chave_texto() -> str:
    """Chave selecionada: CERT_SENHA_KEY (mestre) > SMARTCUT_CERT_KEY (desktop)."""
    from config import settings  # import local evita ciclo no import

    if settings.cert_senha_key:
        return settings.cert_senha_key.strip()
    # Item 10.4: fonte única de configuração (settings) — o Electron injeta
    # SMARTCUT_CERT_KEY via variável de ambiente, lida pelo pydantic.
    return settings.smartcut_cert_key.strip()


def chave_disponivel() -> bool:
    return bool(_chave_texto())


def _chave_bytes() -> bytes:
    chave = _chave_texto()
    if not chave:
        raise ValueError("Chave de cifragem de segredos não configurada (defina CERT_SENHA_KEY no ambiente).")
    # Aceita os dois formatos gerados na documentação: 64 chars hex ou
    # base64url de 32 bytes (43-44 chars).
    if len(chave) == 64:
        try:
            return bytes.fromhex(chave)
        except ValueError:
            pass
    try:
        dec = base64.urlsafe_b64decode(chave + "==")
        if len(dec) == 32:
            return dec
    except Exception:
        pass
    raise ValueError(
        "CERT_SENHA_KEY/SMARTCUT_CERT_KEY inválida: esperada chave de 32 bytes (base64url ou hex de 64 caracteres)."
    )


def cifrar_segredo(plano: str) -> str:
    """Cifra `plano` e retorna o blob `enc:v1:<iv_b64>:<dados_b64>`."""
    if not isinstance(plano, str):
        raise TypeError("cifrar_segredo espera str")
    iv = os.urandom(_IV_BYTES)
    dados = AESGCM(_chave_bytes()).encrypt(iv, plano.encode("utf-8"), None)
    return (
        _PREFIXO + base64.urlsafe_b64encode(iv).decode("ascii") + ":" + base64.urlsafe_b64encode(dados).decode("ascii")
    )


def decifrar_segredo(armazenado: str | None) -> str:
    """Decifra um blob `enc:v1:...`; mantém compatibilidade com valores legados
    (base64 reversível) devolvendo-os em texto claro (sem chave necessária).
    Retorna '' para valores vazios/ilegíveis — nunca lança."""
    if not armazenado:
        return ""
    if armazenado.startswith(_PREFIXO):
        try:
            _b64iv, _b64dados = armazenado[len(_PREFIXO) :].split(":", 1)
            iv = base64.urlsafe_b64decode(_b64iv)
            dados = base64.urlsafe_b64decode(_b64dados)
            return AESGCM(_chave_bytes()).decrypt(iv, dados, None).decode("utf-8")
        except Exception:
            return ""  # chave errada/corrompido: trata como indisponível
    # Legado: o campo armazenava base64(b64encode(senha)).
    try:
        return base64.b64decode(armazenado).decode("utf-8")
    except Exception:
        return ""


def migrar_segredos_legados(db) -> int:
    """Re-cifra senhas legadas (formato base64 reversível) que estejam no banco,
    usando a chave ativa. Retorna quantos registros foram migrados.

    Sem chave disponível retorna 0 (o valor legado segue usável em leitura até
    haver chave — ver docstring do módulo). Chamado no startup (main.py)."""
    from sqlalchemy import select

    from models.venda import Empresa

    if not chave_disponivel():
        return 0
    empresas = db.execute(select(Empresa).where(Empresa.certificado_senha.isnot(None))).scalars().all()
    migrados = 0
    for emp in empresas:
        valor = emp.certificado_senha
        if valor and not valor.startswith(_PREFIXO):
            plano = decifrar_segredo(valor)  # legado: só base64, sem chave
            if plano:
                emp.certificado_senha = cifrar_segredo(plano)
                migrados += 1
    if migrados:
        db.commit()
    return migrados
