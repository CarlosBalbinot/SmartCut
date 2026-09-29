"""encaixe_remove_tecido_legado

Remove encaixes.tecido_id — FK legada para a tabela "tecidos", cujo model
ORM foi removido: com a coluna no model, qualquer INSERT em encaixes falhava
com NoReferencedTableError. A informação de tecido do encaixe vem do lote
(encaixes.lote_id → lotes_tecido → cores_tecido → modelos_tecido).

A tabela "tecidos" em si NÃO é removida (dados legados ficam no banco).

Também torna encaixes.numero (ENC-XXX) único. A numeração antiga era
COUNT(*)+1 e podia repetir; antes da UNIQUE, números duplicados existentes
são renumerados — o encaixe mais antigo mantém o número, os demais recebem
MAX+1 em ordem de criação.

Revision ID: e1c7a4b90d2f
Revises: f8a6f7ef2ccf
Create Date: 2026-09-28 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1c7a4b90d2f'
down_revision: Union[str, None] = 'f8a6f7ef2ccf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UQ_NOME = "uq_encaixes_numero"


def _renumerar_duplicados() -> None:
    bind = op.get_bind()
    linhas = bind.execute(
        sa.text("SELECT id, numero FROM encaixes WHERE numero IS NOT NULL ORDER BY criado_em, id")
    ).all()
    proximo = max((r.numero for r in linhas), default=0) + 1
    vistos: set[int] = set()
    atualizacoes = []
    for r in linhas:
        if r.numero in vistos:
            atualizacoes.append({"b_id": r.id, "b_numero": proximo})
            proximo += 1
        else:
            vistos.add(r.numero)
    if atualizacoes:
        # id sem tipo: volta exatamente como foi lido (texto hex no SQLite,
        # uuid no Postgres).
        encaixes = sa.table("encaixes", sa.column("id"), sa.column("numero", sa.Integer()))
        bind.execute(
            encaixes.update().where(encaixes.c.id == sa.bindparam("b_id")).values(numero=sa.bindparam("b_numero")),
            atualizacoes,
        )


def upgrade() -> None:
    _renumerar_duplicados()
    # SQLite: o batch recria a tabela sem a coluna e sem a FK que dependia
    # dela. Postgres: DROP COLUMN derruba a FK junto.
    with op.batch_alter_table("encaixes") as batch_op:
        batch_op.drop_column("tecido_id")
        batch_op.create_unique_constraint(UQ_NOME, ["numero"])


def downgrade() -> None:
    with op.batch_alter_table("encaixes") as batch_op:
        batch_op.drop_constraint(UQ_NOME, type_="unique")
        batch_op.add_column(sa.Column("tecido_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_encaixes_tecido_id_tecidos", "tecidos", ["tecido_id"], ["id"], ondelete="SET NULL"
        )
