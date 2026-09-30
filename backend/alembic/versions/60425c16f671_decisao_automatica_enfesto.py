"""decisao_automatica_enfesto

Decisão automática do enfesto (F2): o sistema escolhe o tipo de enfesto
(enfesto simples / enfesto duplo) e o modo de camadas de cada lote.

modelos_tecido:
  - tem_direcao (bool, padrão false): tecido com estampa ou pelo não pode
    ser virado — o enfesto é sempre simples.

ordens_corte:
  - tipo_enfesto: MESMA_FACE | FACE_A_FACE | MISTO (decidido na geração;
    nulo nas OCs geradas antes — que foram todas de enfesto simples).
  - decisao_enfesto (JSON): alternativas avaliadas, métricas e motivo.
  - enfesto_avancado (JSON): escolha manual do "Avançado" (nulo = automático).
  - modo_camadas continua existindo e passa a guardar o modo DECIDIDO.

Revision ID: 60425c16f671
Revises: e9a0c1b2d3e4
Create Date: 2026-09-30 09:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60425c16f671'
down_revision: Union[str, None] = 'e9a0c1b2d3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("modelos_tecido") as batch_op:
        batch_op.add_column(sa.Column("tem_direcao", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("ordens_corte") as batch_op:
        batch_op.add_column(sa.Column("tipo_enfesto", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("decisao_enfesto", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("enfesto_avancado", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ordens_corte") as batch_op:
        batch_op.drop_column("enfesto_avancado")
        batch_op.drop_column("decisao_enfesto")
        batch_op.drop_column("tipo_enfesto")
    with op.batch_alter_table("modelos_tecido") as batch_op:
        batch_op.drop_column("tem_direcao")
