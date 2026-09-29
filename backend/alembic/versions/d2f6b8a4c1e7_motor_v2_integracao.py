"""motor_v2_integracao

M2a — motor v2 na Ordem de Corte e no Encaixe Rápido.

configuracao_empresa (Configurações > Produção):
  motor_encaixe            "v2" (padrão) | "v1"
  comprimento_max_mesa_cm  maior mesa de corte da fábrica (200)
  alerta_economia_pct      economia mínima para sugerir a mesa maior (5)

ordens_corte:
  qualidade      RAPIDO | EQUILIBRADO (padrão) | MAXIMO — tempo do v2
  sugestao_mesa  alerta de mesa maior (JSON, nulo = sem sugestão)

Linhas existentes recebem os padrões pelo server_default.

Revision ID: d2f6b8a4c1e7
Revises: c4d8e2a6f1b3
Create Date: 2026-09-29 09:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2f6b8a4c1e7'
down_revision: Union[str, None] = 'c4d8e2a6f1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("configuracao_empresa") as batch_op:
        batch_op.add_column(sa.Column("motor_encaixe", sa.String(5), server_default="v2", nullable=False))
        batch_op.add_column(sa.Column("comprimento_max_mesa_cm", sa.Integer(), server_default="200", nullable=False))
        batch_op.add_column(sa.Column("alerta_economia_pct", sa.Numeric(5, 2), server_default="5.00", nullable=False))
    with op.batch_alter_table("ordens_corte") as batch_op:
        batch_op.add_column(sa.Column("qualidade", sa.String(20), server_default="EQUILIBRADO", nullable=False))
        batch_op.add_column(sa.Column("sugestao_mesa", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ordens_corte") as batch_op:
        batch_op.drop_column("sugestao_mesa")
        batch_op.drop_column("qualidade")
    with op.batch_alter_table("configuracao_empresa") as batch_op:
        batch_op.drop_column("alerta_economia_pct")
        batch_op.drop_column("comprimento_max_mesa_cm")
        batch_op.drop_column("motor_encaixe")
