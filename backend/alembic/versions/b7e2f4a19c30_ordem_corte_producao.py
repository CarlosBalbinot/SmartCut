"""ordem_corte_producao

Linha do tempo da produção na OC (enviada_em/iniciada_em/concluida_em +
cortador) e o consumo de estoque amarrado à OC.

consumos_lote ganha:
  ordem_corte_id       — a OC que baixou o peso (SET NULL: OC deletada não
                          pode apagar o histórico do estoque)
  tipo                 — CONSUMO (baixa) | ESTORNO (devolve)
  estorno_de_id        — o CONSUMO que este ESTORNO desfaz. Precisa para
                          concluir/reabrir em ciclo: sem o vínculo, a 2ª
                          reabertura não sabe qual baixa devolver.
  peso_consumido_kg    — kg que saiu/entrou no estoque (o que o estorno
                          devolve). peso_planejado_kg segue sendo a referência
                          do planejamento da OC.

As OCs existentes continuam válidas: as quatro colunas novas de
ordens_corte são nullable e as de consumos_lote têm default/nullable.
O peso reservado não é coluna do lote — é calculado na consulta (soma do
planejado das OCs ENVIADA/EM_CORTE), então não há backfill aqui.

Revision ID: b7e2f4a19c30
Revises: a3b5c7d9e1f2
Create Date: 2026-09-28 13:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e2f4a19c30'
down_revision: Union[str, None] = 'a3b5c7d9e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Batch mode (renomeia a tabela, recria, copia) porque o SQLite não
    # aceita ADD COLUMN com CONSTRAINT — sem isso o create_foreign_key estoura
    # "near \"CONSTRAINT\": syntax error" e a migration fica pela metade.
    with op.batch_alter_table("ordens_corte") as batch_op:
        batch_op.add_column(sa.Column("enviada_em", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("iniciada_em", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("concluida_em", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("cortador", sa.String(length=150), nullable=True))

    with op.batch_alter_table("consumos_lote") as batch_op:
        batch_op.add_column(sa.Column("ordem_corte_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("tipo", sa.String(length=20), server_default="CONSUMO", nullable=False))
        batch_op.add_column(sa.Column("estorno_de_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("peso_consumido_kg", sa.Numeric(precision=10, scale=3), nullable=True))
        batch_op.create_foreign_key(
            "fk_consumos_lote_ordem_corte", "ordens_corte", ["ordem_corte_id"], ["id"], ondelete="SET NULL"
        )
        # Auto-referência: o ESTORNO aponta para o CONSUMO que desfaz. O
        # SQLite resolve o nome da tabela no CREATE, então precisa existir
        # durante a recriação — por isso a coluna entra antes da constraint.
        batch_op.create_foreign_key(
            "fk_consumos_lote_estorno_de", "consumos_lote", ["estorno_de_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index("ix_consumos_lote_ordem_corte", ["ordem_corte_id"])


def downgrade() -> None:
    with op.batch_alter_table("consumos_lote") as batch_op:
        batch_op.drop_index("ix_consumos_lote_ordem_corte")
        batch_op.drop_constraint("fk_consumos_lote_estorno_de", type_="foreignkey")
        batch_op.drop_constraint("fk_consumos_lote_ordem_corte", type_="foreignkey")
        batch_op.drop_column("peso_consumido_kg")
        batch_op.drop_column("estorno_de_id")
        batch_op.drop_column("tipo")
        batch_op.drop_column("ordem_corte_id")

    with op.batch_alter_table("ordens_corte") as batch_op:
        batch_op.drop_column("cortador")
        batch_op.drop_column("concluida_em")
        batch_op.drop_column("iniciada_em")
        batch_op.drop_column("enviada_em")
