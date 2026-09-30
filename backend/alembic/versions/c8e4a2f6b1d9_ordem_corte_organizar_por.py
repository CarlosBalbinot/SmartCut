"""ordem_corte_organizar_por

ordens_corte:
  - organizar_por (varchar 10, PRODUTO | COR): como a OC organiza o corte.
    PRODUTO (padrão das OCs novas) corta cada produto à parte — um risco nunca
    mistura produtos; COR é o comportamento anterior: tudo o que usa o mesmo
    lote de tecido entra no mesmo risco.

As OCs que já existem ficam em COR: foram geradas assim, e regerar uma delas
deve dar o mesmo resultado de antes.

Revision ID: c8e4a2f6b1d9
Revises: b3d7f1a94c20
Create Date: 2026-09-30 19:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8e4a2f6b1d9"
down_revision: str = "b3d7f1a94c20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("ordens_corte") as batch_op:
        batch_op.add_column(sa.Column("organizar_por", sa.String(10), server_default="PRODUTO", nullable=False))
    op.execute("UPDATE ordens_corte SET organizar_por = 'COR'")


def downgrade() -> None:
    with op.batch_alter_table("ordens_corte") as batch_op:
        batch_op.drop_column("organizar_por")
