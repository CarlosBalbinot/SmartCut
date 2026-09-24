from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

MASCARA_PADRAO = "{GRUPO}-{SEQ}-{COR}-{TAM}"


class ConfiguracaoGrade(Base):
    __tablename__ = "configuracao_grade"

    # Singleton — sempre id=1, ver services/grade_service.obter_configuracao.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)
    mascara: Mapped[str] = mapped_column(String(100), nullable=False, default=MASCARA_PADRAO)
    separador: Mapped[str] = mapped_column(String(5), nullable=False, default="-")
    tamanho_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
