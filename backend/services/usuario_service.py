"""Serviço de usuários do sistema administrativo.

Senha e JWT têm implementação ÚNICA em services/auth_service.py (item 1.2);
aqui ficam apenas as regras de negócio do usuário e aliases de
compatibilidade usados pelos routers (auth.py, usuarios.py).
"""

from sqlalchemy.orm import Session

from models.usuario import Permissao, Usuario
from services import auth_service as _auth

# Alias de compatibilidade: routers/auth.py e routers/usuarios.py chamam
# usuario_service.criar_token/hash_senha/verificar_senha. Atribuição explícita
# (e não só import) mantém os nomes exportados no módulo — o ruff F401 não
# remove esses aliases como faria com um import sem uso interno.
criar_token = _auth.criar_token_admin
hash_senha = _auth.hash_senha
verificar_senha = _auth.verificar_senha


# ── Permissões ─────────────────────────────────────────────────────────


def listar_permissoes(db: Session, usuario_id: int) -> list[dict]:
    permissoes = (
        db.query(Permissao)
        .filter(Permissao.usuario_id == usuario_id, Permissao.permitido == True)  # noqa: E712 — expressão SQL
        .all()
    )
    return [{"modulo": p.modulo, "acao": p.acao} for p in permissoes]


# Item 5.1: módulo fiscal de execução → ação que os routers NF-e exigem.
# O `"ver"` no banco (concedido antes da correção) só dava leitura; a
# execução passa a exigir a ação mapeada aqui.
MODULOS_ACAO_EXECUCAO_FISCAL = {
    "fiscal_transmitir": "executar",
    "fiscal_cancelar": "cancelar",
    "fiscal_carta_correcao": "criar",
}


def sincronizar_permissoes_fiscais(db: Session) -> int:
    """Garante a ação de execução para quem já tinha `ver` nos módulos de
    execução fiscal (item 5.1). Idempotente e executada no boot, cobre os
    bancos existentes (SQLite local e Postgres no Docker) e os novos, sem
    remover nenhuma permissão. Retorna quantas linhas foram criadas."""
    criadas = 0
    for modulo, acao_exec in MODULOS_ACAO_EXECUCAO_FISCAL.items():
        pares_ver = (
            db.query(Permissao)
            .filter(
                Permissao.modulo == modulo,
                Permissao.acao == "ver",
                Permissao.permitido == True,  # noqa: E712 — expressão SQL
            )
            .all()
        )
        for p in pares_ver:
            ja_tem = (
                db.query(Permissao)
                .filter(
                    Permissao.usuario_id == p.usuario_id,
                    Permissao.modulo == modulo,
                    Permissao.acao == acao_exec,
                    Permissao.permitido == True,  # noqa: E712 — expressão SQL
                )
                .first()
            )
            if ja_tem is None:
                db.add(
                    Permissao(
                        usuario_id=p.usuario_id,
                        modulo=modulo,
                        acao=acao_exec,
                        permitido=True,
                    )
                )
                criadas += 1
    if criadas:
        db.commit()
    return criadas


def usuario_para_dict(db: Session, usuario: Usuario) -> dict:
    return {
        "id": usuario.id,
        "username": usuario.username,
        "nome_completo": usuario.nome_completo,
        "is_admin": usuario.is_admin,
        "permissoes": listar_permissoes(db, usuario.id),
    }
