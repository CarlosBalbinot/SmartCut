"""plano_corte_multicor

Plano de corte por produto (PC1 · Passo 3): enfesto multicor.

encaixe_camadas (nova): as camadas de cada cor/lote num encaixe multicor —
  encaixe_id, lote_id, ordem, cor, camadas e peso_kg / custo / comp_metros de
  UMA camada daquele lote (cada tecido tem gramatura, largura, encolhimento e
  preço próprios). Encaixe sem linhas = um lote só, como sempre foi.

configuracao_empresa:
  - tolerancia_tecido_pct (numeric 5,2, padrão 2): "Tolerância de tecido para
    simplificar o corte" — quanto de tecido a mais que o menor consumo o plano
    aceita para usar menos mesas e desenhos.

Revision ID: d5f1b3a7c9e2
Revises: c8e4a2f6b1d9
Create Date: 2026-09-30 19:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d5f1b3a7c9e2"
down_revision: str = "c8e4a2f6b1d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "encaixe_camadas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("encaixe_id", sa.Uuid(), nullable=False),
        sa.Column("lote_id", sa.Uuid(), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cor", sa.String(length=100), nullable=True),
        sa.Column("camadas", sa.Integer(), nullable=False),
        sa.Column("comp_metros", sa.Numeric(8, 3), nullable=True),
        sa.Column("peso_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("custo", sa.Numeric(12, 2), nullable=True),
        sa.ForeignKeyConstraint(["encaixe_id"], ["encaixes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lote_id"], ["lotes_tecido.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_encaixe_camadas_encaixe_id", "encaixe_camadas", ["encaixe_id"])
    op.create_index("ix_encaixe_camadas_lote_id", "encaixe_camadas", ["lote_id"])
    with op.batch_alter_table("configuracao_empresa") as batch_op:
        batch_op.add_column(
            sa.Column("tolerancia_tecido_pct", sa.Numeric(5, 2), server_default="2.00", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("configuracao_empresa") as batch_op:
        batch_op.drop_column("tolerancia_tecido_pct")
    op.drop_index("ix_encaixe_camadas_lote_id", table_name="encaixe_camadas")
    op.drop_index("ix_encaixe_camadas_encaixe_id", table_name="encaixe_camadas")
    op.drop_table("encaixe_camadas")
