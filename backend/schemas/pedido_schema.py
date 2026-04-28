import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


# ── Linha de pedido_pecas ─────────────────────────────────────────────

class PedidoPecaCreate(BaseModel):
    molde_id: uuid.UUID
    quantidade: int = Field(..., gt=0)
    cor: str | None = Field(None, max_length=50)
    lote: str | None = Field(None, max_length=50)


class PedidoPecaOut(BaseModel):
    id: uuid.UUID
    molde_id: uuid.UUID
    quantidade: int
    cor: str | None
    lote: str | None

    model_config = {"from_attributes": True}


# ── Adição em lote por grupo × tamanho ───────────────────────────────

class AdicionarGrupoPecaCreate(BaseModel):
    """Adiciona ao pedido todos os moldes de um grupo com quantidades por tamanho."""
    grupo_id: uuid.UUID
    quantidades: dict[str, int]
    # Hierarquia nova — cor da peça
    cor_id: uuid.UUID | None = None
    # FK legada
    tecido_id: uuid.UUID | None = None


# ── Tecidos do pedido ─────────────────────────────────────────────────

class PedidoTecidoCreate(BaseModel):
    # Hierarquia nova — adiciona pelo lote
    lote_id: uuid.UUID | None = None
    # FK legada — mantida para compatibilidade
    tecido_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def ao_menos_um(self) -> "PedidoTecidoCreate":
        if not self.lote_id and not self.tecido_id:
            raise ValueError("Informe lote_id ou tecido_id.")
        return self


# ── Criação / atualização de pedido ──────────────────────────────────

class PedidoCreate(BaseModel):
    num_pedido: str = Field(..., max_length=50)
    data_pedido: date
    cliente: str | None = Field(None, max_length=150)
    tecido_ids: list[uuid.UUID] = Field(default_factory=list)


class PedidoUpdate(BaseModel):
    data_pedido: date | None = None
    cliente: str | None = Field(None, max_length=150)


class PedidoStatusUpdate(BaseModel):
    status: str = Field(..., max_length=30)


# ── Saída básica (listagem) ───────────────────────────────────────────

class PedidoOut(BaseModel):
    id: uuid.UUID
    num_pedido: str
    data_pedido: date
    cliente: str | None
    status: str
    criado_em: datetime
    total_grupos: int = 0

    model_config = {"from_attributes": True}


# ── Saída detalhada (página de detalhe) ──────────────────────────────

class TecidoInfo(BaseModel):
    pt_id: str                      # id do registro pedido_tecidos (para remoção)
    id: str                         # id do lote ou tecido legado
    nome: str                       # "Maxxi — Preto" ou nome legado
    largura_util_cm: float
    gramatura_g_m2: float
    valor_por_kg: float
    encolhimento_pct: float
    # Campos extras para lotes (None para registros legados)
    lote_id: str | None = None
    codigo_lote: str | None = None
    cor_id: str | None = None
    modelo_nome: str | None = None
    nome_cor: str | None = None
    peso_disponivel_kg: float | None = None


class GrupoPecaOut(BaseModel):
    """Linha agrupada para exibição: um grupo × um tamanho × uma quantidade."""
    grupo_id: uuid.UUID
    grupo_nome: str
    tamanho: str
    quantidade: int
    tecido_id: uuid.UUID | None = None
    tecido_nome: str | None = None
    cor_id: uuid.UUID | None = None


class PedidoDetalheOut(BaseModel):
    id: uuid.UUID
    num_pedido: str
    data_pedido: date
    cliente: str | None
    status: str
    criado_em: datetime
    tecidos: list[TecidoInfo]
    grupos_pecas: list[GrupoPecaOut]


# ── Resumo de corte ───────────────────────────────────────────────────

class ResumoCorteItem(BaseModel):
    molde_id: uuid.UUID
    molde_nome: str
    grupo_nome: str
    peca: str | None
    tamanho: str | None
    tipo_corte: str
    quantidade_producao: int
    quantidade_corte: int
    area_cm2: float | None
    tecido_id: str | None = None
    tecido_nome: str | None = None


class EstimativaTecido(BaseModel):
    tecido_id: str
    tecido_nome: str
    area_cm2: float
    estimativa_metros: float
    estimativa_peso_kg: float
    estimativa_custo: float


class ResumoCorteOut(BaseModel):
    itens: list[ResumoCorteItem]
    total_pecas_corte: int
    total_area_cm2: float
    estimativa_metros: float | None
    estimativa_peso_kg: float | None
    estimativa_custo: float | None
    estimativa_por_tecido: list[EstimativaTecido]
