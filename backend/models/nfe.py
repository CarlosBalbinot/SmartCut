import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

STATUS_VALIDOS = (
    "Rascunho",
    "Aguardando",
    "Autorizada",
    "Rejeitada",
    "Cancelada",
    "Denegada",
)


class NotaFiscal(Base):
    __tablename__ = "notas_fiscais"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # pedidos_venda.id é UUID (não Integer) — corrigido em relação à
    # especificação original para bater com o PK real da tabela.
    pedido_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pedidos_venda.id"), nullable=True
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    serie: Mapped[str] = mapped_column(String(10), nullable=False)
    modelo: Mapped[str] = mapped_column(String(2), nullable=False, default="55")
    ambiente: Mapped[str] = mapped_column(String(20), nullable=False)
    chave_acesso: Mapped[str | None] = mapped_column(String(44), nullable=True)
    protocolo: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Rascunho")
    # Preenchido em montar_xml_nfe (vNF do XML) — usado para exibir o valor
    # na listagem sem precisar reabrir e reparsear o XML a cada consulta.
    valor_nf: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    xml_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    danfe_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    data_emissao: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    data_saida: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    hora_saida: Mapped[str | None] = mapped_column(String(8), nullable=True)
    data_autorizacao: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    motivo_rejeicao: Mapped[str | None] = mapped_column(Text, nullable=True)
    carta_correcao: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pedido: Mapped["PedidoVenda | None"] = relationship(back_populates="notas_fiscais")  # noqa: F821
