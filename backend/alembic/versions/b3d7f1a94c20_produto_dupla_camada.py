"""produto_dupla_camada

Campo de cadastro que diz se o produto é de DUPLA CAMADA (forrado) — é o
único jeito de o sistema saber, e é o que faz a produção preferir enfesto
duplo quando o consumo de tecido empatar.

produtos:
  - dupla_camada (bool, padrão false): produto forrado (legging/camisa de
    duas camadas de tecido). Não tem relação com "peça em par" (costas
    direita e esquerda), que quase toda legging tem e que NÃO a torna dupla.

Por quê: a regra anterior deduzia "produto dupla" de ter peças em par (ou de
as quantidades darem camadas pares). Na OC-0002, MAXXI VERDE MILITAR era
LEGGING FLARE — peça em par, não forrada — e por isso saía em enfesto duplo.

Revision ID: b3d7f1a94c20
Revises: 7c1d4e9a5b02
Create Date: 2026-09-30 16:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3d7f1a94c20"
down_revision: str = "7c1d4e9a5b02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("produtos") as batch_op:
        batch_op.add_column(
            sa.Column("dupla_camada", sa.Boolean(), server_default=sa.false(), nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("produtos") as batch_op:
        batch_op.drop_column("dupla_camada")
