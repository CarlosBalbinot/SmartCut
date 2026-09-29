"""ordem_corte

Ordem de Corte (OC) por pedido: ordens_corte, itens_ordem_corte (snapshot
dos itens do pedido) e ordem_corte_tecidos (lote escolhido por produto+cor).
Encaixe ganha ordem_corte_id (pedido_id segue para rastreio).

1 OC não cancelada por pedido: índice único parcial
uq_ordens_corte_pedido_ativa (WHERE status <> 'CANCELADA').

Revision ID: a3b5c7d9e1f2
Revises: e1c7a4b90d2f
Create Date: 2026-09-28 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b5c7d9e1f2'
down_revision: Union[str, None] = 'e1c7a4b90d2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ATIVA = sa.text("status <> 'CANCELADA'")


def upgrade() -> None:
    op.create_table(
        "ordens_corte",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("pedido_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("modo_camadas", sa.String(length=20), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("pedido_hash", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedidos_venda.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("numero"),
    )
    op.create_index(
        "uq_ordens_corte_pedido_ativa",
        "ordens_corte",
        ["pedido_id"],
        unique=True,
        sqlite_where=_ATIVA,
        postgresql_where=_ATIVA,
    )

    op.create_table(
        "itens_ordem_corte",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ordem_corte_id", sa.Uuid(), nullable=False),
        sa.Column("item_pedido_id", sa.Uuid(), nullable=True),
        sa.Column("numero_item", sa.Integer(), nullable=False),
        sa.Column("sku_id", sa.Integer(), nullable=True),
        sa.Column("produto_pai_id", sa.Uuid(), nullable=False),
        sa.Column("cor", sa.String(length=100), nullable=True),
        sa.Column("tamanho", sa.String(length=100), nullable=True),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("grupo_molde_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["ordem_corte_id"], ["ordens_corte.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sku_id"], ["produtos_sku.id"]),
        sa.ForeignKeyConstraint(["produto_pai_id"], ["produtos.id"]),
        sa.ForeignKeyConstraint(["grupo_molde_id"], ["grupos_molde.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ordem_corte_tecidos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ordem_corte_id", sa.Uuid(), nullable=False),
        sa.Column("produto_pai_id", sa.Uuid(), nullable=False),
        sa.Column("cor", sa.String(length=100), nullable=True),
        sa.Column("lote_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["ordem_corte_id"], ["ordens_corte.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["produto_pai_id"], ["produtos.id"]),
        sa.ForeignKeyConstraint(["lote_id"], ["lotes_tecido.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ordem_corte_id", "produto_pai_id", "cor", name="uq_ordem_corte_tecidos_produto_cor"),
    )

    with op.batch_alter_table("encaixes") as batch_op:
        batch_op.add_column(sa.Column("ordem_corte_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_encaixes_ordem_corte_id", "ordens_corte", ["ordem_corte_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("encaixes") as batch_op:
        batch_op.drop_constraint("fk_encaixes_ordem_corte_id", type_="foreignkey")
        batch_op.drop_column("ordem_corte_id")
    op.drop_table("ordem_corte_tecidos")
    op.drop_table("itens_ordem_corte")
    op.drop_index("uq_ordens_corte_pedido_ativa", table_name="ordens_corte")
    op.drop_table("ordens_corte")
