import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class GrupoMolde(Base):
    __tablename__ = "grupos_molde"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    codigo: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    moldes: Mapped[list["Molde"]] = relationship(  # noqa: F821
        back_populates="grupo", order_by="Molde.peca, Molde.tamanho"
    )
