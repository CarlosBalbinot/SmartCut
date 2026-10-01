"""sequencias

F0, passo 1a: numerações atômicas.

sequencias (nova): uma linha por sequência (nome, valor = último número
  entregue). services/sequencia_service.py incrementa com
  UPDATE ... SET valor = valor + 1 RETURNING valor.

A tabela nasce vazia: cada sequência é criada no primeiro uso a partir do
maior número já gravado, calculado pelo próprio service com a regra que ele
já usava (ver sequencia_service.proximo(..., inicial=...)). Assim a regra do
"maior código" fica num lugar só, e as sequências por grupo/prefixo (que
nascem junto com cada grupo novo) seguem o mesmo caminho das fixas.

Revision ID: b2e8d4f6a1c3
Revises: d5f1b3a7c9e2
Create Date: 2026-10-01 20:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2e8d4f6a1c3"
down_revision: str = "d5f1b3a7c9e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sequencias",
        sa.Column("nome", sa.String(100), primary_key=True),
        sa.Column("valor", sa.BigInteger(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("sequencias")
