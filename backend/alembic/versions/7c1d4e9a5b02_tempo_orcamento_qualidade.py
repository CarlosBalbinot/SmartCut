"""tempo_orcamento_qualidade

A qualidade "Automático" do encaixe passa a ser resolvida por ORÇAMENTO DE
TEMPO, e não mais pelo número de peças do risco.

configuracao_empresa:
  - tempo_maximo_oc_s (int, padrão 300): orçamento de segundos de uma Ordem de
    Corte. Cada risco começa no perfil Rápido e sobe um degrau (Equilibrado,
    Máximo) enquanto sobrar tempo dentro deste limite.

Por quê: com a regra anterior (≤ 80 peças → Máximo) a OC-0004 — 8 riscos de 30,
25, 15 e 5 peças — foi gerada no perfil Máximo e levou 33 minutos para um
resultado idêntico ao do perfil Rápido em 4,4 minutos (5,84 m de risco nos dois
casos). O spyrrow trabalha em segundos inteiros com piso de 1 s por chamada,
então o custo é o número de chamadas, e subir o perfil só compra tempo.

Revision ID: 7c1d4e9a5b02
Revises: 60425c16f671
Create Date: 2026-09-30 14:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c1d4e9a5b02"
down_revision: str = "60425c16f671"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("configuracao_empresa") as batch_op:
        batch_op.add_column(
            sa.Column("tempo_maximo_oc_s", sa.Integer(), server_default="300", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("configuracao_empresa") as batch_op:
        batch_op.drop_column("tempo_maximo_oc_s")
