"""item_pedido_numero_item

Número sequencial fixo do item dentro do pedido (itens_pedido.numero_item,
único por pedido) e o contador pedidos_venda.ultimo_numero_item, que nunca
volta (itens são removidos fisicamente — max() reaproveitaria números).

Itens existentes são numerados 1, 2, 3… dentro de cada pedido pela ordem de
criação. itens_pedido não tem created_at e o id é UUID4 (aleatório), então
a ordem de criação vem do que cada banco guarda da inserção:
  - SQLite:   rowid (cresce a cada INSERT)
  - Postgres: ctid (posição física; ordem de inserção salvo linhas
              atualizadas depois — melhor aproximação disponível)
  - outros:   id

Revision ID: f8a6f7ef2ccf
Revises: f9d6a18fef75
Create Date: 2026-09-24 14:55:35.169616

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a6f7ef2ccf'
down_revision: Union[str, None] = 'f9d6a18fef75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UQ_NOME = "uq_itens_pedido_pedido_numero_item"


def _chave_ordem(dialeto: str):
    """Coluna SQL que reflete a ordem de inserção e como ordenar o valor lido."""
    if dialeto == "sqlite":
        return "rowid", lambda v: v
    if dialeto == "postgresql":
        # ctid vem como texto "(bloco,posição)" — ordena numericamente.
        return "ctid::text", lambda v: tuple(int(x) for x in v.strip("()").split(","))
    return "id", str


def upgrade() -> None:
    with op.batch_alter_table("pedidos_venda") as batch_op:
        batch_op.add_column(sa.Column("ultimo_numero_item", sa.Integer(), server_default="0", nullable=False))
    with op.batch_alter_table("itens_pedido") as batch_op:
        batch_op.add_column(sa.Column("numero_item", sa.Integer(), nullable=True))

    # ── Numeração dos itens existentes ────────────────────────────────────
    bind = op.get_bind()
    coluna_ordem, chave = _chave_ordem(bind.dialect.name)
    linhas = bind.execute(sa.text(f"SELECT id, pedido_id, {coluna_ordem} AS ordem FROM itens_pedido")).all()
    linhas.sort(key=lambda r: (str(r.pedido_id), chave(r.ordem)))

    # id sem tipo: vai de volta exatamente como foi lido (texto hex no
    # SQLite, uuid no Postgres).
    itens = sa.table("itens_pedido", sa.column("id"), sa.column("numero_item", sa.Integer()))
    atualizacoes = []
    pedido_atual, numero = None, 0
    for r in linhas:
        if r.pedido_id != pedido_atual:
            pedido_atual, numero = r.pedido_id, 0
        numero += 1
        atualizacoes.append({"b_id": r.id, "b_numero": numero})
    if atualizacoes:
        bind.execute(
            itens.update().where(itens.c.id == sa.bindparam("b_id")).values(numero_item=sa.bindparam("b_numero")),
            atualizacoes,
        )

    # Contador = maior número atual de cada pedido (0 sem itens).
    op.execute(
        "UPDATE pedidos_venda SET ultimo_numero_item = COALESCE("
        "(SELECT MAX(numero_item) FROM itens_pedido WHERE itens_pedido.pedido_id = pedidos_venda.id), 0)"
    )

    # ── Obrigatório + único por pedido ────────────────────────────────────
    with op.batch_alter_table("itens_pedido") as batch_op:
        batch_op.alter_column("numero_item", existing_type=sa.Integer(), nullable=False)
        batch_op.create_unique_constraint(UQ_NOME, ["pedido_id", "numero_item"])


def downgrade() -> None:
    with op.batch_alter_table("itens_pedido") as batch_op:
        batch_op.drop_constraint(UQ_NOME, type_="unique")
        batch_op.drop_column("numero_item")
    with op.batch_alter_table("pedidos_venda") as batch_op:
        batch_op.drop_column("ultimo_numero_item")
