from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

SITUACAO_VALIDAS = ("Ativa", "Inativa")


class TabelaGrade(Base):
    __tablename__ = "tabelas_grade"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    descricao: Mapped[str] = mapped_column(String(100), nullable=False)
    situacao: Mapped[str] = mapped_column(String(10), nullable=False, default="Ativa")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    itens: Mapped[list["ItemTabelaGrade"]] = relationship(
        back_populates="tabela",
        cascade="all, delete-orphan",
        order_by="ItemTabelaGrade.ordem, ItemTabelaGrade.descricao",
    )


class ItemTabelaGrade(Base):
    __tablename__ = "itens_tabela_grade"
    __table_args__ = (UniqueConstraint("tabela_id", "codigo_curto"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tabela_id: Mapped[int] = mapped_column(Integer, ForeignKey("tabelas_grade.id", ondelete="CASCADE"), nullable=False)
    codigo_curto: Mapped[str] = mapped_column(String(4), nullable=False)
    descricao: Mapped[str] = mapped_column(String(100), nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    situacao: Mapped[str] = mapped_column(String(10), nullable=False, default="Ativa")

    tabela: Mapped["TabelaGrade"] = relationship(back_populates="itens")
