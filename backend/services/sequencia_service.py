"""Sequências atômicas (F0, passo 1a).

`proximo(db, nome)` entrega o próximo número de uma sequência com
`UPDATE sequencias SET valor = valor + 1 WHERE nome = :nome RETURNING valor`:
o incremento acontece no banco, então duas sessões ao mesmo tempo nunca
recebem o mesmo número (no SQLite a segunda espera a primeira terminar; no
PostgreSQL a linha fica travada até o commit). Funciona igual nos dois bancos.

Nada aqui faz commit: o número é consumido na transação de quem chama. Se
ela for desfeita (rollback), o número volta e não sobra buraco.

Sequência que ainda não existe é criada no primeiro uso, a partir de
`inicial(db)` — o maior número já usado, calculado com a mesma regra que o
service usava antes (MAX + 1, maior código etc.). A criação usa
`INSERT ... ON CONFLICT DO NOTHING`: se duas sessões criarem juntas, uma
insere, a outra ignora e as duas incrementam a mesma linha.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import case, select, update
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from models.sequencia import Sequencia

# inicial(db) → último valor já usado (0 se nenhum).
Inicial = Callable[[Session], int]

_tabela = Sequencia.__table__


def _incrementar(db: Session, nome: str) -> int | None:
    return db.execute(
        update(_tabela).where(_tabela.c.nome == nome).values(valor=_tabela.c.valor + 1).returning(_tabela.c.valor)
    ).scalar_one_or_none()


def _criar(db: Session, nome: str, valor: int) -> None:
    """Cria a sequência com `valor`; se outra sessão já criou, não faz nada."""
    dialeto = postgresql if db.get_bind().dialect.name == "postgresql" else sqlite
    db.execute(dialeto.insert(_tabela).values(nome=nome, valor=valor).on_conflict_do_nothing(index_elements=["nome"]))


def proximo(db: Session, nome: str, inicial: Inicial | None = None) -> int:
    """Próximo número de `nome`, sem commit. Na primeira vez, a sequência
    começa depois de `inicial(db)` (ou de 0)."""
    valor = _incrementar(db, nome)
    if valor is None:
        _criar(db, nome, inicial(db) if inicial else 0)
        valor = _incrementar(db, nome)
    return valor


def atual(db: Session, nome: str, inicial: Inicial | None = None) -> int:
    """Último número entregue, sem consumir (pré-visualização: o próximo é
    `atual + 1`, mas outra sessão pode pegá-lo antes)."""
    valor = db.execute(select(_tabela.c.valor).where(_tabela.c.nome == nome)).scalar_one_or_none()
    if valor is None:
        return inicial(db) if inicial else 0
    return valor


def garantir_minimo(db: Session, nome: str, valor: int, inicial: Inicial | None = None) -> None:
    """Garante que a sequência não entregue mais nenhum número <= `valor`
    (ex.: código digitado à mão). Nunca diminui a sequência; sem commit."""
    subir = (
        update(_tabela)
        .where(_tabela.c.nome == nome)
        .values(valor=case((_tabela.c.valor < valor, valor), else_=_tabela.c.valor))
    )
    if db.execute(subir).rowcount == 0:
        # Sequência nova: cria e sobe de novo (outra sessão pode tê-la criado
        # com um valor menor no meio-tempo).
        _criar(db, nome, inicial(db) if inicial else 0)
        db.execute(subir)
