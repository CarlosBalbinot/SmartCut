import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

SITUACAO_VALIDAS = ("Ativo", "Inativo")


class ProdutoSKU(Base):
    __tablename__ = "produtos_sku"
    __table_args__ = (
        UniqueConstraint("produto_pai_id", "linha_item_id", "coluna_item_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # produtos.id é UUID (não Integer) — ver desvio de plano no relatório final.
    produto_pai_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False
    )
    linha_item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("itens_tabela_grade.id", ondelete="RESTRICT"), nullable=True
    )
    coluna_item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("itens_tabela_grade.id", ondelete="RESTRICT"), nullable=True
    )
    codigo: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    preco_venda: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    preco_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    situacao: Mapped[str] = mapped_column(String(10), nullable=False, default="Ativo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    produto_pai: Mapped["Produto"] = relationship(back_populates="skus")  # noqa: F821
    linha_item: Mapped["ItemTabelaGrade | None"] = relationship(foreign_keys=[linha_item_id])  # noqa: F821
    coluna_item: Mapped["ItemTabelaGrade | None"] = relationship(foreign_keys=[coluna_item_id])  # noqa: F821

    @property
    def linha_item_descricao(self) -> str | None:
        return self.linha_item.descricao if self.linha_item else None

    @property
    def coluna_item_descricao(self) -> str | None:
        return self.coluna_item.descricao if self.coluna_item else None
