"""comprimento_max_enfesto

Comprimento máximo (cm) de cada encaixe da OC — o tamanho da mesa em que o
tecido é aberto na produção. É um LIMITE: risco menor sai com o comprimento
que precisar; risco maior é dividido em partes <= limite (nesting_service).

OCs existentes recebem 150 (server_default preenche as linhas atuais).

Revision ID: c4d8e2a6f1b3
Revises: b7e2f4a19c30
Create Date: 2026-09-28 14:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d8e2a6f1b3'
down_revision: Union[str, None] = 'b7e2f4a19c30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Batch mode: o SQLite não aceita ADD COLUMN com CHECK constraint.
    with op.batch_alter_table("ordens_corte") as batch_op:
        batch_op.add_column(sa.Column("comprimento_max_cm", sa.Integer(), server_default="150", nullable=False))
        batch_op.create_check_constraint(
            "ck_ordens_corte_comprimento_max_cm", "comprimento_max_cm BETWEEN 50 AND 2000"
        )


def downgrade() -> None:
    with op.batch_alter_table("ordens_corte") as batch_op:
        batch_op.drop_constraint("ck_ordens_corte_comprimento_max_cm", type_="check")
        batch_op.drop_column("comprimento_max_cm")
