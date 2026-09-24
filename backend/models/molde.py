import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Molde(Base):
    __tablename__ = "moldes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    arquivo_path: Mapped[str | None] = mapped_column(String(500))
    formato: Mapped[str | None] = mapped_column(String(10))
    # parte dentro do grupo: Frente, Costa, Manga...
    peca: Mapped[str | None] = mapped_column(String(100))
    tamanho: Mapped[str | None] = mapped_column(String(10))  # PP P M G GG XGG
    sentido_fio: Mapped[str | None] = mapped_column(String(20))
    # simples | par | par_sem_espelho
    tipo_corte: Mapped[str] = mapped_column(String(20), default="simples")
    rotacao_base: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    area_cm2: Mapped[float | None] = mapped_column(Numeric(10, 4))
    geometria_json: Mapped[dict | None] = mapped_column(JSON)
    grupo_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("grupos_molde.id", ondelete="SET NULL"),
        nullable=True,
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    grupo: Mapped["GrupoMolde | None"] = relationship(  # noqa: F821
        back_populates="moldes"
    )
