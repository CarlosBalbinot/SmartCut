from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

MODULOS_VALIDOS = (
    "cadastros_clientes", "cadastros_produtos", "cadastros_transportadoras",
    "cadastros_vendedores", "tecidos", "moldes", "encaixe_rapido", "encaixes",
    "precificacao", "projecao",
    "pedidos_criar", "pedidos_editar", "pedidos_ver", "pedidos_excluir",
    "pedidos_emitir_nfe",
    "financeiro_painel", "financeiro_fluxo", "financeiro_compras",
    "financeiro_vendas", "financeiro_contabilidade",
    "fiscal_nfe", "fiscal_transmitir", "fiscal_cancelar", "fiscal_carta_correcao",
    "configuracoes_ver", "configuracoes_editar",
    "usuarios_admin",
)

# Item 5.1: "executar" e "cancelar" são as ações de execução dos módulos
# fiscais (fiscal_transmitir/fiscal_cancelar) — o router NF-e antes exigia
# "ver" para essas operações de escrita, o que deixava qualquer usuário com
# leitura fiscal transmitir/cancelar notas.
ACOES_VALIDAS = (
    "ver", "criar", "editar", "excluir", "usar", "imprimir", "confirmar", "gerar",
    "executar", "cancelar",
)


class Usuario(Base):
    """Usuário do sistema administrativo (SmartCut desktop).

    Distinto do `models.painel_vendedor.Usuario` (login do portal do
    vendedor, tabela `usuarios`) — por isso a tabela aqui é
    `usuarios_sistema`, para não colidir.
    """
    __tablename__ = "usuarios_sistema"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    nome_completo: Mapped[str] = mapped_column(String(150), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    ultimo_acesso: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    permissoes: Mapped[list["Permissao"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )


class Permissao(Base):
    __tablename__ = "permissoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios_sistema.id", ondelete="CASCADE"), nullable=False
    )
    modulo: Mapped[str] = mapped_column(String(50), nullable=False)
    acao: Mapped[str] = mapped_column(String(20), nullable=False)
    permitido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Referência direta à classe (não por nome) — evita ambiguidade com
    # models.painel_vendedor.Usuario, que também se chama "Usuario" no
    # mesmo registro declarativo do SQLAlchemy.
    usuario: Mapped["Usuario"] = relationship(Usuario, back_populates="permissoes")
