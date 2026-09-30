"""remover_motor_v1_qualidade_automatica

Motor v1 removido (Tarefa 1) e qualidade Automática (Tarefa 4).

configuracao_empresa:
  - remove motor_encaixe ("v1" | "v2") — o motor de encaixe agora é só o
    v2 (spyrrow + OR-Tools); não há mais seleção nem motor reserva.

ordens_corte:
  - qualidade: server_default passa de EQUILIBRADO para AUTOMATICO.
    Linhas existentes mantêm o perfil que já gravaram (o padrão só vale
    para OC novas — trocar o que já foi gerado não refaz o encaixe).

downgrade recria motor_encaixe com "v2" e volta o server_default.

Revision ID: e9a0c1b2d3e4
Revises: d2f6b8a4c1e7
Create Date: 2026-09-29 11:47:07.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9a0c1b2d3e4'
down_revision: Union[str, None] = 'd2f6b8a4c1e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("configuracao_empresa") as batch_op:
        batch_op.drop_column("motor_encaixe")
    with op.batch_alter_table("ordens_corte") as batch_op:
        batch_op.alter_column("qualidade", server_default="AUTOMATICO", existing_type=sa.String(20))


def downgrade() -> None:
    with op.batch_alter_table("ordens_corte") as batch_op:
        batch_op.alter_column("qualidade", server_default="EQUILIBRADO", existing_type=sa.String(20))
    with op.batch_alter_table("configuracao_empresa") as batch_op:
        batch_op.add_column(sa.Column("motor_encaixe", sa.String(5), server_default="v2", nullable=False))
