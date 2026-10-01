"""Sequências numéricas do sistema (F0, passo 1a).

Uma linha por sequência (`oc`, `encaixe`, `grupo_produto`,
`produto:<grupo_id>`, ...), com o último valor entregue. Só é lida e
gravada por services/sequencia_service.py, que incrementa no SQL
(`UPDATE ... SET valor = valor + 1 RETURNING valor`): duas sessões nunca
recebem o mesmo número.
"""

from sqlalchemy import BigInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Sequencia(Base):
    __tablename__ = "sequencias"

    nome: Mapped[str] = mapped_column(String(100), primary_key=True)
    # Último valor entregue (o próximo é valor + 1).
    valor: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
