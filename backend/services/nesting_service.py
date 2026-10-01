"""nesting_service.py — Lógica de negócio para geração automática de encaixes.

Fluxo (gerar_de_entradas — comum ao Encaixe Rápido e à Ordem de Corte):
  1. Recebe a lista neutra de entradas (lote, molde, quantidade), montada
     por montar_pares_legado (Encaixe Rápido) ou
     ordem_corte_service.montar_pares_oc (OC).
  2. Agrupa por lote de tecido (_agrupar_por_lote) — organizar_por = COR.
     Com organizar_por = PRODUTO o caminho é o plano de corte por produto
     (_montar_plano_corte, enfesto multicor); ver a seção dele.
  3. Para cada lote:
       0. Decide o enfesto (_decidir_lote + nesting_v2/decisor.py): enfesto
          simples ou enfesto duplo × sem sobra ou menos enfestos. Cada
          alternativa válida é simulada no perfil RAPIDO (sem gravar, com
          cache por enfesto) e fica a de menor consumo, com as regras da
          produção no empate; a escolha manual do "Avançado" pula isso.
       a. Planeja os enfestos (services/plano_enfesto.py): camadas e
          conjuntos de cada tamanho, no modo SEM_SOBRA ou MENOS_ENFESTOS
          (camadas pares no enfesto duplo com peça em par).
       b. Para cada enfesto, monta os polígonos (conjuntos × multiplicador
          de tipo_corte) e roda o motor v2 (services/nesting_v2 — spyrrow +
          OR-Tools): uma mesa = um encaixe.
       c. Calcula comp_metros, peso_kg, custo_total e desperdicio_pct com
          aplicação do encolhimento e monta o Encaixe na sessão (sem gravar).
  4. Numera (MAX+1) e grava todos os encaixes num único commit — erro em
     qualquer lote descarta tudo.
  5. Retorna os resumos dos encaixes, avisos e o plano de cada lote.

Motor (v2) — a qualidade (QUALIDADES) define os orçamentos de tempo do
spyrrow; AUTOMATICO distribui o orçamento de tempo da Ordem de Corte entre os
riscos (services/planejamento/custo.py). Falha ou tempo do motor → UMA nova
tentativa com outra
semente e perfil RAPIDO; se falhar de novo, ErroNesting (job vira ERRO e nada
é gravado). O motor aceita um callback de progresso — é por ele que
nesting_jobs mostra a mesa atual e cancela (GeracaoCancelada), sem gravar.
"""

from __future__ import annotations

import logging
import math
import time
import uuid
from collections.abc import Callable, Hashable
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from models.encaixe import Encaixe, EncaixeCamada
from models.grupo_molde import GrupoMolde
from models.molde import Molde
from models.ordem_corte import COMPRIMENTO_MAX_PADRAO_CM, QUALIDADE_PADRAO
from models.pedido import ItemPedido, PedidoVenda as Pedido
from models.tecido import CorTecido, LoteTecido, ModeloTecido
from services import nesting_v2, sequencia_service
from services.erros import ERRO, ErroApp
from services.nesting_v2 import decisor
from services.nesting_v2.geometria import espelha_segunda_copia
from services.gramatura_service import aplicar_encolhimento, calcular_custo, metros_para_peso
from services.plano_enfesto import linhas_enfesto, planejar
from services.planejamento import estimador as planejamento_estimador
from services.planejamento import plano_corte
from services.planejamento.custo import Orcamento, estimar_segundos
from services.precificacao_service import get_ou_criar_config

logger = logging.getLogger(__name__)

# Multiplicador de corte por tipo_corte (mesmo mapeamento usado no pedido de venda)
_MULT: dict[str, int] = {"simples": 1, "par": 2, "par_sem_espelho": 2}

# ── Motor e qualidade ────────────────────────────────────────────────────────

# Qualidade → orçamentos do v2 (segundos por chamada do spyrrow e teto brando
# da geração). EQUILIBRADO é o padrão do M1-B (PRETO 150: ~110 s, 5,69 m).
# O spyrrow trabalha em segundos inteiros com piso de 1 s, então o RAPIDO
# corta o polimento (reencaixe final) para chegar a ~30% do tempo.
QUALIDADES: dict[str, dict[str, float]] = {
    "RAPIDO": {"segundos_mesa": 1.0, "segundos_polimento": 0.0, "segundos_faixa": 10.0, "tempo_max_s": 180.0},
    "EQUILIBRADO": {
        "segundos_mesa": nesting_v2.motor.SEGUNDOS_MESA,
        "segundos_polimento": nesting_v2.motor.SEGUNDOS_POLIMENTO,
        "segundos_faixa": nesting_v2.motor.SEGUNDOS_FAIXA,
        "tempo_max_s": nesting_v2.motor.TEMPO_MAX_S,
    },
    "MAXIMO": {"segundos_mesa": 6.0, "segundos_polimento": 18.0, "segundos_faixa": 90.0, "tempo_max_s": 1800.0},
}
QUALIDADES_PERFIS = ("AUTOMATICO", *QUALIDADES)

# Orçamento de tempo da Ordem de Corte quando não vem da configuração
# (Configurações > Produção > "Tempo limite da ordem de corte (s)"). Ver
# services/planejamento/custo.py — a qualidade AUTOMATICO é resolvida por ele:
# cada risco começa no perfil Rápido (pago pela comparação de enfesto) e sobe
# um degrau enquanto sobrar tempo.
TEMPO_MAXIMO_OC_PADRAO_S = 300

# Fatia da FOLGA do orçamento que a comparação de enfesto pode ficar. A
# comparação não é de graça: ela roda o motor em cada candidato, e esse tempo
# sai da mesma conta do usuário. Mas também não pode competir com o encaixe
# que vem depois — se ela levasse tudo, nenhum risco teria tempo nem para o
# perfil Rápido. Metade e metade: a comparação pode mudar o PLANO (mesas e
# metros, a alavanca maior), o orçamento distribui o resto no GRAU de qualidade.
# Vira 0 (nada de comparação, todos os lotes no padrão seguro) quando o piso do
# pedido já come o limite inteiro.
FOLHA_COMPARACAO = 0.5


class GeracaoCancelada(Exception):
    """Levantada pelo callback de progresso para interromper a geração —
    nunca cai em nova tentativa e nunca grava nada."""


class ErroNesting(ErroApp, RuntimeError):
    """Falha do motor de encaixe (após a nova tentativa) — mensagem legível;
    o job vira ERRO e nenhum encaixe parcial é gravado."""

    def __init__(self, mensagem: str, codigo: str = ERRO, **params):
        super().__init__(codigo, mensagem, 500, **params)


# progresso(fase=..., mesa_atual=..., total_mesas=..., aproveitamento_parcial=...)
Progresso = Callable[..., None]


def config_producao(db: Session) -> dict:
    """Configurações > Produção (singleton configuracao_empresa)."""
    cfg = get_ou_criar_config(db)
    return {
        "comprimento_max_mesa_cm": int(cfg.comprimento_max_mesa_cm),
        "alerta_economia_pct": float(cfg.alerta_economia_pct),
        "tempo_maximo_oc_s": int(cfg.tempo_maximo_oc_s),
        "tolerancia_tecido_pct": float(cfg.tolerancia_tecido_pct),
    }


# Folga (cm) nas comparações com o limite: o topo da peça é recalculado aqui
# com a mesma conta do worker, mas cos/sin do V8 e do CPython podem diferir
# no último bit.
_EPS_CM = 1e-3


# ── DTO normalizado ──────────────────────────────────────────────────────────


@dataclass
class TecidoNesting:
    """Dados normalizados para nesting, independente de nova hierarquia ou legado."""

    nome: str
    largura_util_cm: float
    gramatura_g_m2: float
    valor_por_kg: float
    encolhimento_pct: float
    max_camadas: int
    lote_id: uuid.UUID | None  # nova hierarquia
    tecido_id: uuid.UUID | None  # legado
    # Estampa ou pelo: não pode ser virado → enfesto sempre simples.
    tem_direcao: bool = False

    @classmethod
    def de_lote(cls, lote: LoteTecido) -> "TecidoNesting":
        cor: CorTecido = lote.cor
        modelo: ModeloTecido = cor.modelo
        return cls(
            nome=f"{modelo.nome} — {cor.nome_cor}",
            largura_util_cm=float(cor.largura_util_cm),
            gramatura_g_m2=float(cor.gramatura_g_m2),
            valor_por_kg=float(lote.valor_kg),
            encolhimento_pct=float(cor.encolhimento_pct),
            max_camadas=int(modelo.max_camadas),
            lote_id=lote.id,
            tecido_id=None,
            tem_direcao=bool(modelo.tem_direcao),
        )

    @classmethod
    def de_tecido_legado(cls, tecido: object) -> "TecidoNesting":
        return cls(
            nome=tecido.nome,  # type: ignore[attr-defined]
            largura_util_cm=float(tecido.largura_util_cm),  # type: ignore[attr-defined]
            gramatura_g_m2=float(tecido.gramatura_g_m2),  # type: ignore[attr-defined]
            valor_por_kg=float(tecido.valor_por_kg),  # type: ignore[attr-defined]
            encolhimento_pct=float(tecido.encolhimento_pct),  # type: ignore[attr-defined]
            max_camadas=int(tecido.max_camadas),  # type: ignore[attr-defined]
            lote_id=None,
            tecido_id=tecido.id,  # type: ignore[attr-defined]
        )


# ── Rotações permitidas por sentido do fio ───────────────────────────────────


def _rotacoes(sentido_fio: str | None) -> list[int]:
    """Converte sentido_fio em lista de rotações (graus) permitidas."""
    if sentido_fio == "vertical":
        return [0, 180]
    if sentido_fio == "horizontal":
        return [90, 270]
    if sentido_fio == "45graus":
        return [45, 135, 225, 315]
    return [0, 90, 180, 270]  # sem restrição


# ── Extração de polígono do molde ────────────────────────────────────────────


# ── Extração e saneamento de polígono do molde ───────────────────────────────


class ErroPoligono(ValueError):
    """Geometria do molde inválida e irrecuperável — mensagem cita o molde
    para o bloqueio de geração (Tarefa 2)."""


def _extrair_poligono(molde: Molde) -> list[list[float]]:
    """Extrai o polígono exterior do geometria_json (GeoJSON Polygon ou
    lista legada), em cm. Sem geometria, quadrado aproximado pela área —
    o mesmo fallback que o antigo motor já usava."""
    if molde.geometria_json:
        geo = molde.geometria_json
        if isinstance(geo, dict) and geo.get("type") == "Polygon":
            ring = geo["coordinates"][0]
            return [[float(p[0]), float(p[1])] for p in ring]
        if isinstance(geo, list) and geo:
            return [[float(p[0]), float(p[1])] for p in geo]
    lado = math.sqrt(float(molde.area_cm2)) if molde.area_cm2 and float(molde.area_cm2) > 0 else 10.0
    return [[0.0, 0.0], [lado, 0.0], [lado, lado], [0.0, lado], [0.0, 0.0]]


def _sanear_poligono(pontos: list[list[float]], nome: str) -> list[list[float]]:
    """Valida o anel e tenta corrigir automaticamente com shapely
    (make_valid; fallback buffer(0)) quando o polígono autointersecta.
    Devolve o contorno reparado. Se continuar inválido (menos de 3 pontos,
    área zero ou correção impossível), levanta ErroPoligono citando o molde.
    """
    pts = [[float(x), float(y)] for x, y in pontos]
    if len(pts) < 3:
        raise ErroPoligono(f"Molde '{nome}': geometria sem 3 pontos (polígono inválido).")
    try:
        from shapely.geometry import Polygon
        from shapely.validation import make_valid
    except ImportError:  # pragma: no cover — shapely é dependência do backend
        if _area(pts) <= 1e-6:
            raise ErroPoligono(f"Molde '{nome}': geometria com área zero.")
        return pts
    poly = Polygon(pts)
    # O reparo vem ANTES do teste de área: num polígono autointersectado o
    # shoelace (e Polygon.area) dá a diferença das partes, que vale zero num
    # "bowtie" — sem reparo ele seria rejeitado como área zero.
    if not poly.is_valid:
        for candidato in (make_valid(poly), poly.buffer(0)):
            if candidato.is_empty or candidato.geom_type not in ("Polygon", "MultiPolygon"):
                continue
            if candidato.geom_type == "MultiPolygon":
                partes = [g for g in candidato.geoms if not g.is_empty and g.geom_type == "Polygon"]
                if not partes:
                    continue
                candidato = max(partes, key=lambda g: g.area)
            anel = [list(p) for p in candidato.exterior.coords]
            if len(anel) >= 3 and _area(anel) > 1e-6:
                return anel
        raise ErroPoligono(f"Molde '{nome}': geometria inválida e não pôde ser corrigida automaticamente.")
    if poly.area <= 1e-6:
        raise ErroPoligono(f"Molde '{nome}': geometria com área zero.")
    return [list(p) for p in poly.exterior.coords]


def _poligono(molde: Molde) -> list[list[float]]:
    """Polígono do molde, já saneado (reparo automático de autointerseção)."""
    return _sanear_poligono(_extrair_poligono(molde), _nome_molde(molde))


def _rotate_polygon(pts: list[list[float]], angle_deg: int) -> list[list[float]]:
    """Rotaciona os pontos em torno do centróide do bounding box."""
    if not angle_deg:
        return pts
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    import math as _math

    rad = angle_deg * _math.pi / 180
    cos_a = _math.cos(rad)
    sin_a = _math.sin(rad)
    return [[cx + (x - cx) * cos_a - (y - cy) * sin_a, cy + (x - cx) * sin_a + (y - cy) * cos_a] for x, y in pts]


def _poligono_rotacionado(molde: Molde) -> list[list[float]]:
    """Extrai o polígono e aplica rotacao_base antes de passar ao nesting."""
    pts = _poligono(molde)
    return _rotate_polygon(pts, molde.rotacao_base or 0)


def simetria_molde(geometria_json: dict | list | None, sentido_fio: str | None, rotacao_base: int = 0) -> float:
    """Desvio de simetria (cm) de uma peça do cadastro, com a MESMA medida do
    decisor (decisor.desvio_simetria_cm sobre o polígono e as rotações que o
    motor usa). É o que a tela de moldes usa para avisar peça assimétrica
    marcada como simples ou par sem espelho. Geometria inválida → infinito."""
    molde = Molde(nome="?", geometria_json=geometria_json, sentido_fio=sentido_fio, rotacao_base=rotacao_base or 0)
    try:
        poligono = _poligono_rotacionado(molde)
    except ErroPoligono:
        return float("inf")
    return decisor.desvio_simetria_cm(poligono, tuple(float(r) for r in _rotacoes(sentido_fio)))


# ── Entrada neutra ───────────────────────────────────────────────────────────
#
# Toda geração parte de uma lista neutra de entradas (lote, molde, quantidade)
# — uma entrada por PARTE do molde (frente, costas…) com a quantidade de
# peças inteiras daquele tamanho. Quem monta a lista:
#   montar_pares_legado(pedido)          → Encaixe Rápido (grupo_id/lote_id/qtd_*)
#   ordem_corte_service.montar_pares_oc  → Ordem de Corte (SKU → molde + lote da OC)

Entrada = tuple[LoteTecido, Molde, int]

# (campo de quantidade no ItemPedido, tamanho correspondente do Molde)
TAMANHOS: list[tuple[str, str]] = [
    ("qtd_p", "P"),
    ("qtd_m", "M"),
    ("qtd_g", "G"),
    ("qtd_gg", "GG"),
    ("qtd_g1", "G1"),
    ("qtd_g2", "G2"),
    ("qtd_g3", "G3"),
]


def _norm(texto: str | None) -> str:
    return (texto or "").strip().casefold()


def montar_pares_legado(pedido: Pedido) -> tuple[list[Entrada], list[str]]:
    """Formato do Encaixe Rápido: ItemPedido com grupo_id, lote_id e
    qtd_p..qtd_g3. Itens/tamanhos ignorados viram aviso."""
    entradas: list[Entrada] = []
    avisos: list[str] = []

    for item in pedido.itens:
        nome_grupo = item.grupo.nome if item.grupo else str(item.grupo_id)
        if not item.lote_id or not item.lote:
            avisos.append(f"Peça '{nome_grupo}' sem tecido vinculado — ignorada")
            continue
        if not item.grupo:
            avisos.append(f"Item {item.numero_item:03d} sem grupo de moldes — ignorado")
            continue
        for campo, tamanho in TAMANHOS:
            qtd = getattr(item, campo, 0) or 0
            if qtd <= 0:
                continue
            moldes = [m for m in item.grupo.moldes if _norm(m.tamanho) == _norm(tamanho)]
            if not moldes:
                avisos.append(f"Grupo '{item.grupo.nome}': sem molde tamanho={tamanho} — tamanho ignorado")
                continue
            entradas.extend((item.lote, molde, qtd) for molde in moldes)

    return entradas, avisos


def _agrupar_por_lote(
    entradas: list[Entrada],
) -> dict[uuid.UUID, tuple[TecidoNesting, dict[uuid.UUID, list]]]:
    """{lote_id: (TecidoNesting, {molde_id: [molde, quantidade]})} — a mesma
    parte vinda de itens diferentes (ex.: duas cores no mesmo lote) soma."""
    grupos: dict[uuid.UUID, tuple[TecidoNesting, dict[uuid.UUID, list]]] = {}
    for lote, molde, qtd in entradas:
        if qtd <= 0:
            continue
        if lote.id not in grupos:
            grupos[lote.id] = (TecidoNesting.de_lote(lote), {})
        moldes = grupos[lote.id][1]
        if molde.id in moldes:
            moldes[molde.id][1] += qtd
        else:
            moldes[molde.id] = [molde, qtd]
    return grupos


def _produto_do_molde(molde: Molde) -> tuple[str, str | None]:
    """(chave, nome) do produto do molde, pelo grupo de moldes: o produto pai
    quando o grupo tem um; senão o próprio grupo (Encaixe Rápido legado)."""
    grupo = molde.grupo
    if grupo is None:
        return "", None
    if grupo.produto_id is not None:
        return str(grupo.produto_id), (grupo.produto.descricao if grupo.produto else grupo.nome)
    return f"grupo:{grupo.id}", grupo.nome


# ── Geração de encaixes para um lote ─────────────────────────────────────────


def _chave(molde: Molde) -> tuple:
    """Identifica a peça inteira: grupo de moldes + tamanho."""
    return (molde.grupo_id, _norm(molde.tamanho))


def _rotulo(moldes_da_chave: list[Molde]) -> dict:
    m = moldes_da_chave[0]
    return {"grupo_nome": m.grupo.nome if m.grupo else None, "tamanho": (m.tamanho or "").strip()}


class _Andamento:
    """Progresso acumulado de uma geração (todos os lotes e enfestos):
    mesa_atual/total_mesas contam as mesas já fechadas dos enfestos
    anteriores mais as do enfesto em andamento."""

    def __init__(self, progresso: Progresso | None):
        self.progresso = progresso
        self.mesas_fechadas = 0

    def avisar(self, fase: str, mesa: int = 0, total: int = 0, aproveitamento: float | None = None) -> None:
        if self.progresso is None:
            return
        self.progresso(
            fase=fase,
            mesa_atual=self.mesas_fechadas + mesa,
            total_mesas=self.mesas_fechadas + max(total, mesa),
            aproveitamento_parcial=round(aproveitamento, 4) if aproveitamento is not None else None,
        )


def _quantidades(moldes_qtd: dict[uuid.UUID, list]) -> tuple[dict[tuple, list[Molde]], dict[tuple, int]]:
    """({peça: [moldes]}, {peça: quantidade}) — a peça inteira é grupo +
    tamanho (_chave); a quantidade é a maior entre os moldes dela."""
    por_chave: dict[tuple, list[Molde]] = {}
    qtd_chave: dict[tuple, int] = {}
    for molde, qtd in moldes_qtd.values():
        k = _chave(molde)
        por_chave.setdefault(k, []).append(molde)
        qtd_chave[k] = max(qtd_chave.get(k, 0), qtd)
    return por_chave, qtd_chave


def _tem_par(moldes_qtd: dict[uuid.UUID, list]) -> bool:
    """Há `par` (espelhado)? É o que pede camadas pares no enfesto duplo —
    `par_sem_espelho` são duas peças iguais e não pede."""
    return any((molde.tipo_corte or "simples") == "par" for molde, _ in moldes_qtd.values())


def _dupla_camada(moldes_qtd: dict[uuid.UUID, list]) -> bool:
    """Algum produto do lote é de DUPLA CAMADA (forrado)? Vem do cadastro do
    produto pai (produtos.dupla_camada). Peça em par NÃO conta: quase toda
    legging tem par (costas direita e esquerda) e isso não a torna forrada.
    Um lote pode juntar vários produtos (mesmo lote de tecido em itens de
    produtos diferentes): basta um deles ser forrado."""
    for molde, _ in moldes_qtd.values():
        produto = molde.grupo.produto if molde.grupo else None
        if produto is not None and produto.dupla_camada:
            return True
    return False


def _enfestos_do_lote(
    por_chave: dict[tuple, list[Molde]],
    qtd_chave: dict[tuple, int],
    max_camadas: int,
    *,
    tipo: str,
    modo: str,
    camadas_pares: bool = False,
) -> list[tuple[int, float]]:
    """[(peças físicas, área em cm²)] de cada enfesto do plano (tipo, modo).

    Sai de `planejar`, que é puro: nenhum spyrrow, nenhuma consulta. É o que
    deixa orçar a comparação de enfesto ANTES de pagar a primeira simulação —
    e o que dá os números do perfil de qualidade sem rodar o motor.
    """
    plano = planejar(qtd_chave, max_camadas, modo, camadas_pares=camadas_pares)
    espelhar_par = tipo != decisor.FACE_A_FACE
    saida = []
    for enfesto in plano["enfestos"]:
        pecas = [
            _peca_v2(m, c, espelhar_par) for k, c in enfesto["conjuntos_por_tamanho"].items() for m in por_chave[k]
        ]
        saida.append(
            (
                sum(p.quantidade for p in pecas),
                sum(p.quantidade * _area(p.poligono) for p in pecas),
            )
        )
    return saida


def _custos_candidatos(
    tecido: TecidoNesting,
    moldes_qtd: dict[uuid.UUID, list],
    limite_cm: int,
    lista: list[decisor.Candidato],
) -> list[float]:
    """Segundos estimados (perfil RÁPIDO) de cada candidato, na ordem da lista.

    Serve para duas coisas: pôr a comparação na ordem mais barata primeiro e
    dizer se o tempo que sobrou do orçamento da OC dá para simular.
    """
    por_chave, qtd_chave = _quantidades(moldes_qtd)
    tem_par = _tem_par(moldes_qtd)
    custos = []
    for cand in lista:
        riscos = _enfestos_do_lote(
            por_chave,
            qtd_chave,
            tecido.max_camadas,
            tipo=cand.tipo,
            modo=cand.modo,
            camadas_pares=cand.tipo == decisor.FACE_A_FACE and tem_par,
        )
        custos.append(sum(estimar_segundos(pecas, area, tecido.largura_util_cm, limite_cm) for pecas, area in riscos))
    return custos


def _gerar_para_tecido(
    pedido: Pedido | None,
    tecido: TecidoNesting,
    moldes_qtd: dict[uuid.UUID, list],
    modo: str,
    ordem_corte_id: uuid.UUID | None,
    descricao: str | None,
    limite_cm: int,
    qualidade: str = QUALIDADE_PADRAO,
    andamento: _Andamento | None = None,
    semente: int = 0,
    *,
    tipo_enfesto: str = decisor.MESMA_FACE,
    cache: dict | None = None,
    perfis: dict[int, str] | None = None,
    orcamento: Orcamento | None = None,
    chave_lote: str | None = None,
) -> tuple[list[Encaixe], list[str], dict]:
    """Planeja os enfestos do lote (plano_enfesto) e roda o nesting_v2 de
    cada um — cada mesa do nesting_v2 vira um Encaixe (_enfesto_v2), sempre
    <= limite_cm, com as mesmas camadas do enfesto. Os encaixes saem
    montados, fora da sessão, sem número e sem commit.

    qualidade: perfil de tempo (ver QUALIDADES); "AUTOMATICO" usa o perfil que
    perfis dá para este enfesto (o orçamento de tempo da OC distribuiu antes).
    perfis: {nº do enfesto: perfil} da distribuição do orçamento.
    orcamento: o mesmo Orcamento, para documentar a escolha no mapa_json.
    chave_lote: a chave com que este lote foi registrado no orçamento — é com
    ela que `Orcamento.detalhe` acha o risco. Sem ela (montagem de um risco
    avulso, sem orçamento) não há o que documentar.
    semente: troca entre tentativas (jogada do retry automático).
    tipo_enfesto: MESMA_FACE espelha a 2ª cópia dos pares; FACE_A_FACE não
    espelha e, havendo peça em par, usa camadas pares. cache: resultados do
    motor por enfesto (ver _enfesto_v2), compartilhado entre as simulações da
    decisão e a geração definitiva.

    Retorna (encaixes_montados, avisos, plano).
    """
    andamento = andamento or _Andamento(None)
    avisos: list[str] = []
    perfis = perfis or {}

    por_chave, qtd_chave = _quantidades(moldes_qtd)
    face_a_face = tipo_enfesto == decisor.FACE_A_FACE
    plano = planejar(qtd_chave, tecido.max_camadas, modo, camadas_pares=face_a_face and _tem_par(moldes_qtd))
    rotulos = {k: _rotulo(ms) for k, ms in por_chave.items()}
    encaixes: list[Encaixe] = []

    for n, enfesto in enumerate(plano["enfestos"], start=1):
        camadas = enfesto["camadas"]
        fase = f"{tecido.nome} · enfesto {n}/{len(plano['enfestos'])}"
        extras = {
            "modo_camadas": modo,
            "tipo_enfesto": tipo_enfesto,
            "enfesto": n,
            "total_enfestos": len(plano["enfestos"]),
            "sobra_total": sum(enfesto["sobra_por_tamanho"].values()),
            "comprimento_max_cm": limite_cm,
            "motor_usado": "v2",
            "qualidade": qualidade,
        }
        montados = _enfesto_v2(
            pedido,
            tecido,
            [(m, c) for k, c in enfesto["conjuntos_por_tamanho"].items() for m in por_chave[k]],
            camadas,
            limite_cm,
            perfis.get(n, qualidade),
            extras,
            linhas_enfesto(enfesto, rotulos),
            ordem_corte_id,
            descricao,
            lambda f, mesa, total, aprov, fase=fase: andamento.avisar(f"{fase} · {f}", mesa, total, aprov),
            semente,
            espelhar_par=not face_a_face,
            cache=cache,
            orcamento=orcamento,
            enfesto=(chave_lote, n) if chave_lote is not None else n,
        )
        andamento.mesas_fechadas += len(montados)
        encaixes.extend(montados)

    # A mesma peça grande em vários enfestos gera o mesmo aviso — uma vez só.
    return encaixes, list(dict.fromkeys(avisos)), plano


# ── Decisão do enfesto ───────────────────────────────────────────────────────


class _TempoEsgotado(Exception):
    """A comparação de formas de enfesto passou de TEMPO_COMPARACAO_S."""


def _analisar_lote(tecido: TecidoNesting, moldes_qtd: dict[uuid.UUID, list]) -> decisor.Analise:
    """Classifica as peças do lote e diz se enfesto duplo vale para ele."""
    _, qtd_chave = _quantidades(moldes_qtd)
    natural = planejar(qtd_chave, tecido.max_camadas, "SEM_SOBRA")
    pecas = {
        str(molde.id): decisor.PecaAnalise(
            nome=_nome_molde(molde),
            poligono=_poligono_rotacionado(molde),
            rotacoes=tuple(float(r) for r in _rotacoes(molde.sentido_fio)),
            tipo_corte=molde.tipo_corte or "simples",
        )
        for molde, _ in moldes_qtd.values()
    }
    return decisor.analisar(
        pecas,
        tem_direcao=tecido.tem_direcao,
        camadas_naturais=[e["camadas"] for e in natural["enfestos"]],
        max_camadas=tecido.max_camadas,
        dupla_camada=_dupla_camada(moldes_qtd),
    )


def _decidir_lote(
    tecido: TecidoNesting,
    moldes_qtd: dict[uuid.UUID, list],
    limite_cm: int,
    *,
    tipo_fixo: str | None,
    modo_fixo: str | None,
    semente: int,
    cache: dict,
    prazo: float,
    progresso: Progresso | None,
    motivo_prazo: str | None = None,
    custos: list[float] | None = None,
) -> decisor.Decisao:
    """Escolhe o tipo de enfesto e o modo de camadas de UM lote.

    Cada candidato válido (decisor.candidatos) roda no perfil RAPIDO, sem
    gravar; os resultados do motor ficam no `cache` (enfesto igual em dois
    candidatos não roda duas vezes, e a geração definitiva reaproveita o que
    já estiver no perfil certo).

    Os candidatos são simulados DO MAIS BARATO PARA O MAIS CARO (custo estimado
    por `_custos_candidatos`, que não roda o motor) e um candidato só começa se
    o tempo que resta no `prazo` der para ele. Sem essa checagem, o primeiro
    candidato de um lote grande consome o prazo inteiro e os lotes seguintes
    ficam sem comparação nenhuma — e, como o custo medido depende da máquina,
    a mesma OC saía diferente em execuções diferentes.

    Nenhum candidato avaliado → enfesto simples + sem sobra, com o motivo
    registrado (`motivo_prazo` diz por quê). Escolha manual (tipo e modo fixos)
    não simula nada."""
    inicio = time.monotonic()
    if progresso is not None:
        progresso(fase=f"Analisando as peças… · {tecido.nome}", mesa_atual=0, total_mesas=0)
    analise = _analisar_lote(tecido, moldes_qtd)
    lista = decisor.candidatos(analise, tipo_fixo, modo_fixo)

    if len(lista) == 1:
        escolhido = lista[0]
        motivo = f"{escolhido.rotulo}: escolha manual (Avançado)."
        if tipo_fixo == decisor.FACE_A_FACE and escolhido.tipo != decisor.FACE_A_FACE:
            motivo = f"{escolhido.rotulo}: enfesto duplo pedido no Avançado, mas {analise.motivo_invalida}."
        escolhido.avaliado = False
        return decisor.Decisao(
            tipo=escolhido.tipo,
            modo=escolhido.modo,
            motivo=motivo,
            regra="MANUAL",
            candidatos=lista,
            face_a_face_valida=analise.face_a_face_valida,
            motivo_face_a_face=analise.motivo_invalida,
            classes=analise.classes,
            dupla_camada=analise.dupla_camada,
            manual=True,
        )

    if custos is None:
        custos = _custos_candidatos(tecido, moldes_qtd, limite_cm, lista)
    # Do mais barato para o mais caro: o mesmo segundo decide mais lotes, e a
    # ordem deixa de depender da velocidade da máquina.
    ordem = sorted(range(len(lista)), key=lambda i: (custos[i], i))
    esgotado = False
    for posicao, i in enumerate(ordem, start=1):
        cand = lista[i]
        restante = prazo - time.monotonic()
        if esgotado or restante <= 0 or custos[i] > restante:
            # Não cabe no que sobrou. Como a fila é crescente de custo, nada
            # depois cabe também — marcar todos de uma vez e parar de conferir.
            esgotado = True
            cand.avaliado = False
            continue
        fase = f"Comparando formas de enfesto… · {tecido.nome} · {posicao}/{len(lista)} {cand.rotulo}"

        def _aviso(fase: str = fase, **_estado) -> None:
            if time.monotonic() > prazo:
                raise _TempoEsgotado()
            if progresso is not None:
                progresso(fase=fase, mesa_atual=0, total_mesas=0)

        _aviso()
        t0 = time.monotonic()
        try:
            encaixes, _, plano = _gerar_para_tecido(
                None,
                tecido,
                moldes_qtd,
                cand.modo,
                None,
                None,
                limite_cm,
                "RAPIDO",
                _Andamento(_aviso),
                semente,
                tipo_enfesto=cand.tipo,
                cache=cache,
            )
        except _TempoEsgotado:
            esgotado = True
            cand.avaliado = False
            continue
        except GeracaoCancelada:
            raise
        except Exception as exc:  # noqa: BLE001 — um candidato que falha só sai da disputa
            logger.warning("[NESTING] %s: candidato %s falhou: %s", tecido.nome, cand.rotulo, exc)
            cand.erro = str(exc) or type(exc).__name__
            continue
        t = totais(encaixes)
        cand.metros = t["metros"]
        cand.mesas = t["mesas"]
        cand.enfestos = len(plano["enfestos"])
        cand.camadas = sum(e["camadas"] for e in plano["enfestos"])
        cand.sobra = plano["sobra_total"]
        cand.segundos = round(time.monotonic() - t0, 1)

    # Padrão seguro: enfesto simples + sem sobra no que não foi fixado à mão.
    seguro = (lista[0].tipo if tipo_fixo else decisor.MESMA_FACE, modo_fixo or "SEM_SOBRA")
    if not any(c.avaliado and c.erro is None for c in lista):
        porque = motivo_prazo or f"a comparação passou de {decisor.TEMPO_COMPARACAO_S:g} s"
        decisao = decisor.decisao_padrao_seguro(analise, lista, porque, *seguro)
    else:
        vencedor, motivo, regra = decisor.escolher(lista, analise)
        # Comparação pela metade é melhor que nenhuma: o que sobrou sem simular
        # entra no motivo, senão a tela mostra uma escolha sem lastro.
        pendentes = [c for c in lista if not c.avaliado and c.erro is None]
        if pendentes:
            nomes = ", ".join(c.rotulo.lower() for c in pendentes)
            motivo += (
                f" Comparação incompleta por falta de tempo: {nomes} "
                f"não {'foi simulado' if len(pendentes) == 1 else 'foram simulados'}."
            )
        decisao = decisor.Decisao(
            tipo=vencedor.tipo,
            modo=vencedor.modo,
            motivo=motivo,
            regra=regra,
            candidatos=lista,
            face_a_face_valida=analise.face_a_face_valida,
            motivo_face_a_face=analise.motivo_invalida,
            classes=analise.classes,
            dupla_camada=analise.dupla_camada,
            tempo_esgotado=bool(pendentes),
        )
    decisao.segundos = time.monotonic() - inicio
    logger.info("[NESTING] %s: enfesto %s/%s — %s", tecido.nome, decisao.tipo, decisao.modo, decisao.motivo)
    return decisao


# ── Motor v2: um enfesto → uma mesa por encaixe ──────────────────────────────


def _peca_v2(molde: Molde, conjuntos: int, espelhar_par: bool = True) -> nesting_v2.Peca:
    """Molde → linha de entrada do v2 com o MESMO polígono do v1
    (_poligono_rotacionado, rotacao_base já aplicada — por isso
    rotacao_base=0 aqui) e as mesmas rotações; a quantidade conta as cópias
    físicas (conjuntos × multiplicador do tipo_corte), como no benchmark.
    espelhar_par: False no enfesto duplo (par sem cópia espelhada)."""
    tipo = molde.tipo_corte or "simples"
    return nesting_v2.Peca(
        id=str(molde.id),
        poligono=_poligono_rotacionado(molde),
        quantidade=conjuntos * _MULT.get(tipo, 1),
        rotacoes=tuple(float(r) for r in _rotacoes(molde.sentido_fio)),
        tipo_corte=tipo,
        peca=molde.peca,
        tamanho=(molde.tamanho or "").strip(),
        grupo_nome=molde.grupo.nome if molde.grupo else None,
        espelhar_par=espelhar_par,
    )


def _pecas_parte_v2(mesa: nesting_v2.Mesa, camadas: int) -> list[dict]:
    """Moldes da mesa (nesting_v2.geometria.por_molde: molde_id, peca,
    grupo_nome, tamanho, por_camada, espelhadas, total — as chaves do v1)
    mais a forma curta molde/tamanho/produto/quantidade (por camada)."""
    return [
        {**linha, "molde": linha["peca"], "produto": linha["grupo_nome"], "quantidade": linha["por_camada"]}
        for linha in mesa.moldes(camadas)
    ]


def _enfesto_v2(
    pedido: Pedido | None,
    tecido: TecidoNesting,
    moldes_conjuntos: list[tuple[Molde, int]],
    camadas: int,
    limite_cm: int,
    qualidade: str,
    extras: dict,
    pecas_por_tamanho: list[dict],
    ordem_corte_id: uuid.UUID | None,
    descricao: str | None,
    ao_progresso: Callable[[str, int, int, float | None], None],
    semente: int = 0,
    *,
    espelhar_par: bool = True,
    cache: dict | None = None,
    orcamento: Orcamento | None = None,
    enfesto: Hashable | None = None,
) -> list[Encaixe]:
    """Roda o nesting_v2 num enfesto e monta um Encaixe por mesa.

    mapa_json no formato do v1: placements com o polígono já espelhado na
    metade virada de um `par` + flag `espelhada` para o desenho. A grade do
    enfesto (pecas_por_tamanho, com a sobra do plano) e o resumo do v2 vão
    SÓ na parte 1 — as demais partes têm apenas os moldes delas
    (pecas_parte), para o enfesto não ser somado uma vez por parte.

    qualidade: perfil CONCRETO de tempo (Rápido/Equilibrado/Máximo). O
    "AUTOMATICO" já foi resolvido em _gerar_para_tecido pela distribuição do
    orçamento da OC (services/planejamento/custo.py) — o que a distribuição
    decidiu entra no mapa_json do risco (qualidade_automatica) para dizer por
    que ele ficou neste perfil.
    semente: usada na geração (o retry automático troca para variar o
    resultado e escapar da falha).
    espelhar_par: False no enfesto duplo (ver geometria.espelha_segunda_copia).
    cache: {chave: nesting_v2.Resultado} — o encaixe de um enfesto depende
    só das peças (não das camadas); a chave junta lote, peças, espelho,
    perfil, semente e limite. A simulação da decisão e a geração definitiva
    compartilham o cache.
    orcamento / enfesto: onde a decisão está registrada no mapa_json. `enfesto`
    é a chave do risco no orçamento — no fluxo da OC, (lote, nº do enfesto), e
    não só o nº: é assim que Orcamento.detalhe acha o registro.

    Raises: nesting_v2.ErroEncaixe / qualquer erro do motor (o chamador faz
    a nova tentativa com outro seed e perfil RAPIDO); GeracaoCancelada vem
    de ao_progresso.
    """
    pecas = [_peca_v2(m, c, espelhar_par) for m, c in moldes_conjuntos if c > 0]
    if not pecas:
        return []
    perfil = qualidade if qualidade in QUALIDADES else QUALIDADES["EQUILIBRADO"]
    extras_parte_base = {**extras, "qualidade_perfil": perfil}
    if orcamento is not None:
        detalhe = orcamento.detalhe(enfesto)
        if detalhe:
            extras_parte_base["qualidade_automatica"] = detalhe
    chave = (
        str(tecido.lote_id or tecido.tecido_id),
        tuple(sorted((p.id, p.quantidade, espelha_segunda_copia(p.tipo_corte, p.espelhar_par)) for p in pecas)),
        perfil,
        semente,
        limite_cm,
    )
    resultado = cache.get(chave) if cache is not None else None
    if resultado is None:
        resultado = nesting_v2.gerar(
            pecas,
            tecido.largura_util_cm,
            limite_cm,
            camadas,
            ao_progresso=ao_progresso,
            seed=semente,
            **QUALIDADES.get(perfil, QUALIDADES["EQUILIBRADO"]),
        )
        if cache is not None:
            cache[chave] = resultado
    resumo = {k: v for k, v in resultado.resumo_enfesto().items() if k != "pecas_por_tamanho"}
    total = len(resultado.mesas)
    encaixes: list[Encaixe] = []
    for mesa in resultado.mesas:
        extras_parte = {
            **extras_parte_base,
            "parte_numero": mesa.indice,
            "total_partes": total,
            "pecas_parte": _pecas_parte_v2(mesa, camadas),
            "parts_count": len(mesa.pecas),
        }
        if total > 1:
            extras_parte["parte"] = f"{mesa.indice}/{total}"
        if mesa.indice == 1:
            extras_parte["pecas_por_tamanho"] = pecas_por_tamanho
            extras_parte["resumo_enfesto"] = resumo
        encaixes.append(
            _montar_encaixe(
                pedido,
                tecido,
                {"placements": mesa.pecas, "efficiency": mesa.aproveitamento, "width_used": mesa.comprimento_cm},
                camadas,
                tecido.largura_util_cm,
                parts=[],
                extras=extras_parte,
                ordem_corte_id=ordem_corte_id,
                descricao=descricao,
            )
        )
    return encaixes


# ── Dimensões e área (validação e conferência) ───────────────────────────────


def _dimensoes(poligono: list[list[float]], graus: float) -> tuple[float, float]:
    """(largura, comprimento) do bounding box após a rotação (rotação em
    torno da origem — a mesma convenção usada pelo motor)."""
    rad = graus * math.pi / 180
    c, s = math.cos(rad), math.sin(rad)
    xs = [x * c - y * s for x, y in poligono]
    ys = [x * s + y * c for x, y in poligono]
    return max(xs) - min(xs), max(ys) - min(ys)


def _area(poligono: list[list[float]]) -> float:
    n = len(poligono)
    dobro = sum(poligono[i][0] * poligono[(i + 1) % n][1] - poligono[(i + 1) % n][0] * poligono[i][1] for i in range(n))
    return abs(dobro) / 2


def _nome_molde(molde: Molde | None) -> str:
    if molde is None:
        return "?"
    return (molde.nome or f"{molde.peca or ''} {molde.tamanho or ''}").strip()


# ── Validação antes de gerar (Conferência / Encaixe Rápido) ──────────────────
#
# Bloqueia a geração com o molde e o tecido citados na mensagem, ANTES de o
# motor rodar: peça mais larga que a largura útil do tecido em todas as
# rotações permitidas pelo fio; polígono inválido que não passou no reparo
# automático do shapely. Peça mais comprida que o limite da mesa NÃO bloqueia
# (o risco é dividido em mesas) — vira o aviso ATENÇÃO do Comprimento máximo.


def checar_molde(molde: Molde, lote: LoteTecido | None, comprimento_max_cm: int) -> list[tuple[str, str, bool]]:
    """Problemas de um molde com o tecido do lote.

    Retorna [(codigo, mensagem, bloqueia), ...]:
      * PECA_LARGURA_UTIL — peça mais larga que a largura útil do tecido em
        TODAS as rotações permitidas (bloqueia).
      * POLIGONO_INVALIDO — geometria inválida e irrecuperável (bloqueia).
      * PECA_LIMITE_MESA — peça mais comprida que o limite da mesa; continua
        permitido (o risco é dividido em mesas), apenas avisa.
    Sem lote (sem tecido) não há o que checar aqui — a pendência de tecido
    fica com a conferência.
    """
    if lote is None:
        return []
    nome = _nome_molde(molde)
    tecido_nome = lote.cor.modelo.nome if lote.cor and lote.cor.modelo else lote.codigo_lote
    tecido_rot = f"{tecido_nome} — {lote.cor.nome_cor}" if lote.cor else lote.codigo_lote
    try:
        pts = _poligono_rotacionado(molde)
    except ErroPoligono as exc:
        return [("POLIGONO_INVALIDO", str(exc), True)]
    rots = _rotacoes(molde.sentido_fio) or [0]
    dims = [_dimensoes(pts, r) for r in rots]
    largura_util = float(lote.cor.largura_util_cm)
    menor_largura = min(larg for larg, _ in dims)
    if menor_largura > largura_util + _EPS_CM:
        return [
            (
                "PECA_LARGURA_UTIL",
                f"Molde '{nome}': peça mais larga que a largura útil do tecido "
                f"'{tecido_rot}' ({largura_util:g} cm) em todas as rotações permitidas.",
                True,
            )
        ]
    menor_comprimento = min(comp for _, comp in dims)
    if menor_comprimento > comprimento_max_cm + _EPS_CM:
        return [
            (
                "PECA_LIMITE_MESA",
                f"Molde '{nome}': peça mais comprida que o limite da mesa "
                f"({comprimento_max_cm:g} cm) — o risco será dividido em mesas (ATENÇÃO).",
                False,
            )
        ]
    return []


def validar_entradas(entradas: list[Entrada], comprimento_max_cm: int) -> tuple[list[str], list[str]]:
    """Checa todas as entradas (lote, molde, quantidade) antes de gerar.

    Retorna (problemas_bloqueantes, avisos): mensagens que já citam moldes e
    tecidos; a mesma mensagem repetida de partes iguais aparece uma vez só.
    """
    bloqueiam: list[str] = []
    avisos: list[str] = []
    for lote, molde, _qtd in entradas:
        for _codigo, mensagem, bloqueia in checar_molde(molde, lote, comprimento_max_cm):
            (bloqueiam if bloqueia else avisos).append(mensagem)
    return list(dict.fromkeys(bloqueiam)), list(dict.fromkeys(avisos))


def _montar_encaixe(
    pedido: Pedido | None,
    tecido: TecidoNesting,
    result: dict,
    num_camadas: int,
    largura_cm: float,
    parts: list[dict],
    pecas: list[Molde] | None = None,
    extras: dict | None = None,
    ordem_corte_id: uuid.UUID | None = None,
    descricao: str | None = None,
) -> Encaixe:
    """Calcula métricas e monta o Encaixe FORA da sessão e sem número:
    _gravar adiciona, numera e grava todos juntos numa transação (e a
    simulação de mesa maior só lê os números, sem gravar).

    peso_kg/custo_total são de UMA camada (comprimento do encaixe);
    mapa_json.peso_total_kg = peso_kg × camadas (consumo real do lote)."""

    width_used_cm: float = result["width_used"]
    efficiency: float = result["efficiency"]

    comp_minimo_m = width_used_cm / 100.0
    comp_metros = aplicar_encolhimento(comp_minimo_m, tecido.encolhimento_pct)
    peso_kg = metros_para_peso(comp_metros, tecido.gramatura_g_m2, largura_cm)
    custo_total = calcular_custo(peso_kg, tecido.valor_por_kg)

    desperdicio_pct = max(0.0, (1.0 - efficiency) * 100.0)

    # Enriquecer placements com polígono e metadados do molde
    parts_map: dict[str, list] = {p["id"]: p["polygon"] for p in parts}
    pecas_map: dict[str, dict] = {}
    for molde in pecas or []:
        pecas_map[str(molde.id)] = {
            "peca": molde.peca,
            "tamanho": molde.tamanho,
            "grupo_nome": molde.grupo.nome if molde.grupo else None,
        }

    enriched_placements: list[dict] = []
    for pl in result["placements"]:
        mid = pl["id"]
        entry: dict = {**pl}
        if mid in parts_map:
            entry["polygon"] = parts_map[mid]
        if mid in pecas_map:
            entry.update(pecas_map[mid])
        enriched_placements.append(entry)

    mapa_json: dict = {
        "lote_id": str(tecido.lote_id) if tecido.lote_id else None,
        "tecido_id": str(tecido.tecido_id) if tecido.tecido_id else None,
        "tecido_nome": tecido.nome,
        "largura_cm": largura_cm,
        "comprimento_cm": round(width_used_cm, 3),
        "num_camadas": num_camadas,
        "efficiency": round(efficiency, 4),
        "placements": enriched_placements,
        "parts_count": sum(p["quantity"] for p in parts),
        "peso_total_kg": round(peso_kg * num_camadas, 3),
        **(extras or {}),
    }

    # id explícito: o resumo devolvido ao frontend precisa dele antes do
    # flush (o default do model só é aplicado na gravação).
    encaixe = Encaixe(
        id=uuid.uuid4(),
        pedido_id=pedido.id if pedido else None,
        ordem_corte_id=ordem_corte_id,
        lote_id=tecido.lote_id,
        mapa_json=mapa_json,
        comp_metros=round(comp_metros, 3),
        peso_kg=round(peso_kg, 3),
        custo_total=round(custo_total, 2),
        desperdicio_pct=round(desperdicio_pct, 2),
        num_camadas=num_camadas,
        status="ativo",
        descricao=descricao,
    )
    return encaixe


# ── Numeração e gravação ─────────────────────────────────────────────────────

# Sequência do número ENC-XXX (services/sequencia_service.py, F0 passo 1c).
SEQ_ENCAIXE = "encaixe"


def _ultimo_numero_encaixe(db: Session) -> int:
    """Maior ENC já gravado, inclusive os deletados (soft-delete) — ponto de
    partida da sequência `encaixe` no primeiro uso."""
    return db.query(func.max(Encaixe.numero)).scalar() or 0


def _numerar(db: Session, encaixes: list[Encaixe]) -> None:
    """ENC-XXX pela sequência atômica: duas gerações ao mesmo tempo nunca
    pegam o mesmo número, e um número nunca é reaproveitado."""
    # no_autoflush: o UPDATE da sequência não pode gravar antes os encaixes
    # pendentes (ainda sem número).
    with db.no_autoflush:
        for encaixe in encaixes:
            encaixe.numero = sequencia_service.proximo(db, SEQ_ENCAIXE, _ultimo_numero_encaixe)


def _gravar(db: Session, encaixes: list[Encaixe]) -> None:
    """Numera e grava todos os encaixes da chamada num único commit — junto
    com o que mais estiver pendente na sessão (ex.: encaixes anteriores da
    OC marcados como deletados). Se o commit falhar, quem chama desfaz tudo,
    inclusive os números."""
    _numerar(db, encaixes)
    db.add_all(encaixes)
    db.commit()


def _resumo(encaixe: Encaixe) -> dict:
    mapa = encaixe.mapa_json or {}
    return {
        "id": str(encaixe.id),
        "lote_id": mapa.get("lote_id"),
        "tecido_id": mapa.get("tecido_id"),
        "tecido_nome": mapa.get("tecido_nome"),
        "num_camadas": encaixe.num_camadas,
        "comp_metros": float(encaixe.comp_metros),
        "peso_kg": float(encaixe.peso_kg),
        "peso_total_kg": mapa.get("peso_total_kg") or round(float(encaixe.peso_kg) * (encaixe.num_camadas or 1), 3),
        "custo_total": float(encaixe.custo_total),
        "custo_total_camadas": round(float(encaixe.custo_total) * (encaixe.num_camadas or 1), 2),
        "desperdicio_pct": float(encaixe.desperdicio_pct),
        "aproveitamento_pct": round(100.0 - float(encaixe.desperdicio_pct), 2),
        "total_pecas_plano": mapa.get("parts_count"),
        "enfesto": mapa.get("enfesto"),
        "parte": mapa.get("parte"),
        "parte_numero": mapa.get("parte_numero"),
        "total_partes": mapa.get("total_partes"),
        "comprimento_max_cm": mapa.get("comprimento_max_cm"),
        "pecas_parte": mapa.get("pecas_parte"),
        "pecas_por_tamanho": mapa.get("pecas_por_tamanho"),
        "sobra_total": mapa.get("sobra_total"),
        "motor_usado": mapa.get("motor_usado"),
        "qualidade": mapa.get("qualidade"),
        "qualidade_perfil": mapa.get("qualidade_perfil"),
        "resumo_enfesto": mapa.get("resumo_enfesto"),
        "tipo_enfesto": mapa.get("tipo_enfesto"),
        "modo_camadas": mapa.get("modo_camadas"),
        # Grupo de corte (OC organizada por produto); ausente = o lote.
        "grupo_corte": mapa.get("grupo_corte"),
        "produto_nome": mapa.get("produto_nome"),
        "risco": mapa.get("risco"),
        "camadas_por_cor": mapa.get("camadas_por_cor"),
        "numero_enc": encaixe.numero,
        "descricao": encaixe.descricao,
        # Por que este risco saiu neste perfil (só na qualidade Automático).
        "qualidade_automatica": mapa.get("qualidade_automatica"),
    }


def totais(encaixes: list[Encaixe]) -> dict:
    """Consumo de todas as camadas (comp_metros/peso_kg/custo_total do
    Encaixe são de UMA camada) e quantas mesas foram abertas."""
    return {
        "metros": round(sum(float(e.comp_metros) * (e.num_camadas or 1) for e in encaixes), 3),
        "mesas": len(encaixes),
        "peso_kg": round(sum(float(e.peso_kg) * (e.num_camadas or 1) for e in encaixes), 3),
        "custo": round(sum(float(e.custo_total) * (e.num_camadas or 1) for e in encaixes), 2),
    }


# ── Plano de corte por produto (enfesto multicor) ────────────────────────────
#
# organizar_por = PRODUTO: o corte de cada produto é planejado por
# services/planejamento/plano_corte.py — quais riscos desenhar e quantas
# camadas de CADA COR vão em cada risco. Cores do mesmo modelo de tecido com
# larguras próximas dividem o enfesto; o motor roda UMA vez por risco (não por
# cor) e cada mesa vira um Encaixe com as camadas por cor em encaixe_camadas.


@dataclass
class _GrupoProduto:
    """Um produto num modelo de tecido, com as cores (lotes) que podem dividir
    enfesto (larguras dentro de plano_corte.LARGURA_MAX_DIFERENCA_CM)."""

    chave: str
    produto_id: str
    produto_nome: str | None
    modelo_nome: str
    tem_direcao: bool
    # tamanho → moldes (as partes do produto naquele tamanho)
    por_tamanho: dict[str, list[Molde]]
    # str(lote_id) → tecido do lote
    tecidos: dict[str, TecidoNesting]
    cores: list[plano_corte.CorGrade]
    area_por_tamanho: dict[str, float]

    @property
    def moldes(self) -> list[Molde]:
        return [m for ms in self.por_tamanho.values() for m in ms]

    def rotulo(self) -> str:
        nomes = " + ".join(c.nome for c in self.cores)
        return f"{self.modelo_nome} — {nomes}"


def _agrupar_produto(entradas: list[Entrada]) -> dict[str, _GrupoProduto]:
    """Grupos do plano de corte: (produto, modelo de tecido, faixa de largura).
    A quantidade de uma cor num tamanho é a maior entre as partes do tamanho
    (como _quantidades); a mesma parte vinda de itens diferentes soma."""
    base: dict[tuple, dict] = {}
    for lote, molde, qtd in entradas:
        if qtd <= 0:
            continue
        produto_id, produto_nome = _produto_do_molde(molde)
        modelo = lote.cor.modelo
        g = base.setdefault(
            (produto_id, str(modelo.id)),
            {"produto_nome": produto_nome, "modelo": modelo, "moldes": {}, "lotes": {}, "qtd": {}},
        )
        tam = (molde.tamanho or "").strip()
        g["moldes"].setdefault(tam, {})[molde.id] = molde
        g["lotes"][str(lote.id)] = lote
        chave = (str(lote.id), molde.id)
        g["qtd"][chave] = g["qtd"].get(chave, 0) + qtd

    grupos: dict[str, _GrupoProduto] = {}
    for (produto_id, modelo_id), g in base.items():
        por_tamanho = {t: list(ms.values()) for t, ms in g["moldes"].items()}
        area = {
            t: sum(_area(_poligono_rotacionado(m)) * _MULT.get(m.tipo_corte or "simples", 1) for m in ms)
            for t, ms in por_tamanho.items()
        }
        cores = []
        for lote_id, lote in g["lotes"].items():
            grade = {t: max(g["qtd"].get((lote_id, m.id), 0) for m in ms) for t, ms in por_tamanho.items()}
            cores.append(
                plano_corte.CorGrade(
                    cor=lote_id,
                    grade={t: q for t, q in grade.items() if q > 0},
                    modelo_tecido=modelo_id,
                    largura_cm=float(lote.cor.largura_util_cm),
                    max_camadas=int(g["modelo"].max_camadas),
                    nome=lote.cor.nome_cor,
                )
            )
        for cores_grupo in plano_corte.agrupar_cores(cores):
            menor = min(c.largura_cm for c in cores_grupo)
            chave = f"{produto_id}:{modelo_id}:{menor:g}"
            grupos[chave] = _GrupoProduto(
                chave=chave,
                produto_id=produto_id,
                produto_nome=g["produto_nome"],
                modelo_nome=g["modelo"].nome,
                tem_direcao=bool(g["modelo"].tem_direcao),
                por_tamanho=por_tamanho,
                tecidos={c.cor: TecidoNesting.de_lote(g["lotes"][c.cor]) for c in cores_grupo},
                cores=cores_grupo,
                area_por_tamanho=area,
            )
    return grupos


def _decidir_plano(
    grupo: _GrupoProduto,
    limite_cm: int,
    tolerancia_pct: float,
    tipo_fixo: str | None,
) -> tuple[decisor.Decisao, plano_corte.PlanoCorte]:
    """Enfesto simples × enfesto duplo para o grupo, pelo PLANO (estimativa,
    sem motor): cada tipo válido tem o seu plano de corte — o duplo com peça
    `par` em camadas pares, e a sobra que isso obriga entra na comparação
    (decisor.escolher: menor consumo, empate técnico, sem sobra antes de com
    sobra, regras da produção)."""
    moldes_qtd = {m.id: [m, 0] for m in grupo.moldes}
    tem_par = _tem_par(moldes_qtd)
    planos = {
        decisor.MESMA_FACE: plano_corte.planejar_corte(
            grupo.cores, grupo.area_por_tamanho, limite_mesa_cm=limite_cm, tolerancia_pct=tolerancia_pct
        )
    }
    simples = planos[decisor.MESMA_FACE]
    pecas = {
        str(m.id): decisor.PecaAnalise(
            nome=_nome_molde(m),
            poligono=_poligono_rotacionado(m),
            rotacoes=tuple(float(r) for r in _rotacoes(m.sentido_fio)),
            tipo_corte=m.tipo_corte or "simples",
        )
        for m in grupo.moldes
    }
    analise = decisor.analisar(
        pecas,
        tem_direcao=grupo.tem_direcao,
        camadas_naturais=[sum(e.values()) for r in simples.riscos for e in r.enfestos],
        max_camadas=min(c.max_camadas for c in grupo.cores),
        dupla_camada=_dupla_camada(moldes_qtd),
    )
    tipos = [decisor.MESMA_FACE] + ([decisor.FACE_A_FACE] if analise.face_a_face_valida else [])
    manual = tipo_fixo in decisor.TIPOS
    if manual:
        tipos = [tipo_fixo] if tipo_fixo in tipos else [decisor.MESMA_FACE]
    if decisor.FACE_A_FACE in tipos:
        planos[decisor.FACE_A_FACE] = (
            plano_corte.planejar_corte(
                grupo.cores,
                grupo.area_por_tamanho,
                limite_mesa_cm=limite_cm,
                camadas_pares=True,
                tolerancia_pct=tolerancia_pct,
            )
            if tem_par
            else simples
        )
    lista = []
    for tipo in tipos:
        p = planos[tipo]
        lista.append(
            decisor.Candidato(
                tipo=tipo,
                modo=decisor.PLANO_CORTE,
                metros=round(p.metros, 3),
                mesas=p.mesas,
                enfestos=sum(len(r.enfestos) for r in p.riscos),
                camadas=p.camadas,
                sobra=p.sobra_total,
            )
        )
    if manual:
        escolhido = lista[0]
        motivo = f"{escolhido.rotulo}: escolha manual (Avançado)."
        if tipo_fixo == decisor.FACE_A_FACE and escolhido.tipo != decisor.FACE_A_FACE:
            motivo = f"{escolhido.rotulo}: enfesto duplo pedido no Avançado, mas {analise.motivo_invalida}."
        regra = "MANUAL"
    else:
        escolhido, motivo, regra = decisor.escolher(lista, analise)
    plano = planos[escolhido.tipo]
    decisao = decisor.Decisao(
        tipo=escolhido.tipo,
        modo=decisor.PLANO_CORTE,
        motivo=f"{motivo} Plano de corte: {plano.motivo}",
        regra=regra,
        candidatos=lista,
        face_a_face_valida=analise.face_a_face_valida,
        motivo_face_a_face=analise.motivo_invalida,
        classes=analise.classes,
        dupla_camada=analise.dupla_camada,
        manual=manual,
    )
    return decisao, plano


def _pecas_fisicas(grupo: _GrupoProduto, conjuntos: dict[str, int]) -> tuple[int, float]:
    """(peças físicas, área em cm²) de UMA camada do risco — para o orçamento."""
    pecas = sum(n * _MULT.get(m.tipo_corte or "simples", 1) for t, n in conjuntos.items() for m in grupo.por_tamanho[t])
    return pecas, planejamento_estimador.area_risco(conjuntos, grupo.area_por_tamanho)


def _encaixe_multicor(
    pedido: Pedido | None,
    grupo: _GrupoProduto,
    mesa: nesting_v2.Mesa,
    camadas_por_cor: dict[str, int],
    largura_cm: float,
    extras: dict,
    ordem_corte_id: uuid.UUID | None,
    descricao: str | None,
) -> Encaixe:
    """Uma mesa de um enfesto multicor → Encaixe + uma EncaixeCamada por cor.

    O consumo de cada lote sai do tecido DELE (encolhimento, gramatura, largura
    e preço): o risco é o mesmo, o tecido não. O Encaixe fica com a cor
    principal (mais camadas) em lote_id e com a média ponderada por camada em
    comp_metros / peso_kg / custo_total — o total (× num_camadas) bate com a
    soma das linhas."""
    total = sum(camadas_por_cor.values())
    principal = max(camadas_por_cor, key=lambda c: (camadas_por_cor[c], -list(camadas_por_cor).index(c)))
    encaixe = _montar_encaixe(
        pedido,
        grupo.tecidos[principal],
        {"placements": mesa.pecas, "efficiency": mesa.aproveitamento, "width_used": mesa.comprimento_cm},
        total,
        largura_cm,
        parts=[],
        extras=extras,
        ordem_corte_id=ordem_corte_id,
        descricao=descricao,
    )
    comp_min_m = mesa.comprimento_cm / 100.0
    linhas = []
    soma = {"comp": 0.0, "peso": 0.0, "custo": 0.0}
    nomes = {c.cor: c.nome for c in grupo.cores}
    for ordem, (cor, camadas) in enumerate(camadas_por_cor.items()):
        t = grupo.tecidos[cor]
        comp = aplicar_encolhimento(comp_min_m, t.encolhimento_pct)
        peso = metros_para_peso(comp, t.gramatura_g_m2, t.largura_util_cm)
        custo = calcular_custo(peso, t.valor_por_kg)
        linhas.append(
            EncaixeCamada(
                lote_id=t.lote_id,
                ordem=ordem,
                cor=nomes.get(cor),
                camadas=camadas,
                comp_metros=round(comp, 3),
                peso_kg=round(peso, 3),
                custo=round(custo, 2),
            )
        )
        soma["comp"] += comp * camadas
        soma["peso"] += round(peso, 3) * camadas
        soma["custo"] += round(custo, 2) * camadas
    encaixe.camadas_cor = linhas
    encaixe.comp_metros = round(soma["comp"] / total, 3)
    encaixe.peso_kg = round(soma["peso"] / total, 3)
    encaixe.custo_total = round(soma["custo"] / total, 2)
    encaixe.mapa_json = {
        **encaixe.mapa_json,
        "tecido_nome": f"{grupo.modelo_nome} — {' + '.join(nomes[c] for c in camadas_por_cor)}",
        "peso_total_kg": round(soma["peso"], 3),
        "camadas_por_cor": [
            {"lote_id": str(grupo.tecidos[c].lote_id), "cor": nomes.get(c), "camadas": n}
            for c, n in camadas_por_cor.items()
        ],
    }
    return encaixe


def _montar_plano_corte(
    pedido: Pedido | None,
    grupos: dict[str, _GrupoProduto],
    ordem_corte_id: uuid.UUID | None,
    descricao: str | None,
    limite_cm: int,
    qualidade: str,
    progresso: Progresso | None,
    semente: int = 0,
    *,
    tipo_enfesto: str = decisor.AUTOMATICO,
    escolhas: dict[str, tuple[str, str]] | None = None,
    cache: dict | None = None,
    tempo_maximo_s: float | None = None,
    tolerancia_pct: float = plano_corte.TOLERANCIA_PADRAO_PCT,
) -> tuple[list[Encaixe], list[str], dict[str, dict], dict[str, decisor.Decisao]]:
    """organizar_por = PRODUTO: planeja cada grupo (_decidir_plano), distribui
    o orçamento de tempo entre TODOS os riscos e roda o motor uma vez por
    risco. Mesma assinatura de retorno de _montar_todos; nada vai para a
    sessão. A decisão não roda o motor (é pela estimativa), então nenhum
    tempo do orçamento vai para comparação."""
    andamento = _Andamento(progresso)
    cache = {} if cache is None else cache
    tipo_fixo = None if tipo_enfesto == decisor.AUTOMATICO else tipo_enfesto
    decisoes: dict[str, decisor.Decisao] = {}
    planos_pc: dict[str, plano_corte.PlanoCorte] = {}
    for chave, grupo in grupos.items():
        if progresso is not None:
            progresso(
                fase=f"Planejando o corte… · {grupo.produto_nome} · {grupo.rotulo()}", mesa_atual=0, total_mesas=0
            )
        fixo = escolhas[chave][0] if escolhas and chave in escolhas else tipo_fixo
        decisao, plano = _decidir_plano(grupo, limite_cm, tolerancia_pct, fixo)
        lotes = [str(grupo.tecidos[c.cor].lote_id) for c in grupo.cores]
        decisao.extra = {
            "lote_id": lotes[0],
            "lotes": lotes,
            "tecido": grupo.rotulo(),
            "produto_nome": grupo.produto_nome,
            "plano_corte": {
                **plano.json(),
                "cores": {c.cor: c.nome for c in grupo.cores},
            },
        }
        decisoes[chave], planos_pc[chave] = decisao, plano

    avisos: list[str] = []
    orcamento: Orcamento | None = None
    perfis: dict[tuple[str, int], str] = {}
    if qualidade == QUALIDADE_PADRAO:
        orcamento = Orcamento(TEMPO_MAXIMO_OC_PADRAO_S if tempo_maximo_s is None else float(tempo_maximo_s))
        for chave, plano in planos_pc.items():
            for i, risco in enumerate(plano.riscos, start=1):
                pecas, area = _pecas_fisicas(grupos[chave], risco.conjuntos)
                orcamento.registrar(
                    (chave, i), pecas=pecas, area_cm2=area, largura_cm=risco.largura_cm, limite_cm=limite_cm
                )
        perfis = orcamento.distribuir()
        if orcamento.aviso:
            avisos.append(orcamento.aviso)

    encaixes: list[Encaixe] = []
    planos: dict[str, dict] = {}
    for chave, grupo in grupos.items():
        decisao, plano = decisoes[chave], planos_pc[chave]
        espelhar_par = decisao.tipo != decisor.FACE_A_FACE
        total_enfestos = sum(len(r.enfestos) for r in plano.riscos)
        n_enfesto = 0
        primeiro_do_grupo = True
        for i, risco in enumerate(plano.riscos, start=1):
            perfil = perfis.get((chave, i), qualidade)
            perfil = perfil if perfil in QUALIDADES else "EQUILIBRADO"
            pecas = [
                _peca_v2(m, n, espelhar_par) for t, n in risco.conjuntos.items() for m in grupo.por_tamanho[t] if n > 0
            ]
            fase = f"{grupo.produto_nome} · {grupo.modelo_nome} · risco {i}/{len(plano.riscos)} {risco.rotulo()}"
            # Cache por PROPORÇÃO + LARGURA (e espelho/perfil/semente/limite):
            # o encaixe não depende da cor nem das camadas.
            chave_cache = (
                "plano",
                risco.largura_cm,
                tuple(sorted((p.id, p.quantidade, espelha_segunda_copia(p.tipo_corte, p.espelhar_par)) for p in pecas)),
                perfil,
                semente,
                limite_cm,
            )
            resultado = cache.get(chave_cache)
            if resultado is None:
                resultado = nesting_v2.gerar(
                    pecas,
                    risco.largura_cm,
                    limite_cm,
                    max(sum(e.values()) for e in risco.enfestos),
                    ao_progresso=lambda f, mesa, total, aprov, fase=fase: andamento.avisar(
                        f"{fase} · {f}", mesa, total, aprov
                    ),
                    seed=semente,
                    **QUALIDADES[perfil],
                )
                cache[chave_cache] = resultado
            resumo = {k: v for k, v in resultado.resumo_enfesto().items() if k != "pecas_por_tamanho"}
            total_mesas = len(resultado.mesas)
            for enfesto in risco.enfestos:
                n_enfesto += 1
                camadas = sum(enfesto.values())
                for mesa in resultado.mesas:
                    extras = {
                        "modo_camadas": decisor.PLANO_CORTE,
                        "tipo_enfesto": decisao.tipo,
                        "grupo_corte": chave,
                        "produto_id": grupo.produto_id,
                        "produto_nome": grupo.produto_nome,
                        "risco": i,
                        "total_riscos": len(plano.riscos),
                        "enfesto": n_enfesto,
                        "total_enfestos": total_enfestos,
                        # A sobra é do PLANO: vai uma vez só, no 1º encaixe do grupo.
                        "sobra_total": plano.sobra_total if primeiro_do_grupo else 0,
                        "comprimento_max_cm": limite_cm,
                        "motor_usado": "v2",
                        "qualidade": qualidade,
                        "qualidade_perfil": perfil,
                        "parte_numero": mesa.indice,
                        "total_partes": total_mesas,
                        "pecas_parte": _pecas_parte_v2(mesa, camadas),
                        "parts_count": len(mesa.pecas),
                    }
                    if orcamento is not None:
                        detalhe = orcamento.detalhe((chave, i))
                        if detalhe:
                            extras["qualidade_automatica"] = detalhe
                    if total_mesas > 1:
                        extras["parte"] = f"{mesa.indice}/{total_mesas}"
                    if mesa.indice == 1:
                        extras["pecas_por_tamanho"] = [
                            {
                                "grupo_nome": grupo.por_tamanho[t][0].grupo.nome
                                if grupo.por_tamanho[t][0].grupo
                                else None,
                                "tamanho": t,
                                "conjuntos": n,
                                "pecas": n * camadas,
                                "sobra": 0,
                            }
                            for t, n in risco.conjuntos.items()
                        ]
                        extras["resumo_enfesto"] = resumo
                    enc = _encaixe_multicor(
                        pedido, grupo, mesa, enfesto, risco.largura_cm, extras, ordem_corte_id, descricao
                    )
                    if primeiro_do_grupo:
                        enc.mapa_json = {**enc.mapa_json, "decisao_enfesto": decisao.json()}
                        primeiro_do_grupo = False
                    encaixes.append(enc)
                andamento.mesas_fechadas += total_mesas
        planos[chave] = {"sobra_total": plano.sobra_total, "plano_corte": plano.json()}
    return encaixes, avisos, planos, decisoes


# ── Pontos de entrada públicos ───────────────────────────────────────────────


def _montar_todos(
    pedido: Pedido | None,
    grupos: dict,
    modo: str,
    ordem_corte_id: uuid.UUID | None,
    descricao: str | None,
    limite_cm: int,
    qualidade: str,
    progresso: Progresso | None,
    semente: int = 0,
    *,
    tipo_enfesto: str = decisor.AUTOMATICO,
    escolhas: dict[str, tuple[str, str]] | None = None,
    cache: dict | None = None,
    decisoes: dict[str, decisor.Decisao] | None = None,
    tempo_maximo_s: float | None = None,
) -> tuple[list[Encaixe], list[str], dict[str, dict], dict[str, decisor.Decisao]]:
    """Todos os lotes com o motor v2 — nada vai para a sessão.

    modo / tipo_enfesto: "AUTOMATICO" decide cada lote (_decidir_lote); um
    valor fixo é a escolha manual do "Avançado". escolhas: {lote_id: (tipo,
    modo)} já decididos (a simulação da mesa maior repete a decisão da
    geração, sem comparar de novo). decisoes: onde guardar as decisões —
    passado de uma tentativa para a outra, o retry não refaz a comparação.
    O prazo da comparação é uma FATIA DO ORÇAMENTO DA OC, não um relógio à
    parte: metade do que sobrar depois do piso de encaixe, e nunca mais que
    decisor.TEMPO_COMPARACAO_S (ver FOLHA_COMPARACAO).
    tempo_maximo_s: orçamento de tempo da qualidade AUTOMATICO (ver
    Orcamento), contando desde o começo da geração — a comparação de enfesto
    entra como piso já pago. Um perfil fixo escolhido no "Avançado" não usa
    orçamento, mas a comparação continua limitada por ele.

    Retorna (encaixes, avisos, planos, decisoes)."""
    andamento = _Andamento(progresso)
    cache = {} if cache is None else cache
    decisoes = {} if decisoes is None else decisoes
    encaixes: list[Encaixe] = []
    avisos: list[str] = []
    planos: dict[str, dict] = {}
    # 1º decide todos os lotes (só as comparações contam no prazo), depois
    # encaixa de verdade — senão o encaixe definitivo de um lote comeria o
    # prazo da comparação do lote seguinte.
    t_decisao = time.monotonic()
    tipo_fixo = None if tipo_enfesto == decisor.AUTOMATICO else tipo_enfesto
    modo_fixo = None if modo == decisor.AUTOMATICO else modo

    # A comparação de enfesto RODA O MOTOR, então ela sai do orçamento do
    # usuário — não de um relógio à parte. Antes de pagar a primeira simulação,
    # `_custos_candidatos` (puro, sem motor) diz quanto cada candidato custa e
    # qual é o PISO de cada lote: o plano mais barato possível. O que sobrar do
    # limite depois do piso é o que dá para comparar.
    #
    # Medido na OC-0004 (3 lotes, 324 peças): o piso (306 s estimados) já
    # estourava o limite de 300 s, e a comparação gastou 180 s para escolher...
    # o próprio padrão seguro. Aqui ela vira 0 s e a OC sai com a mesma
    # resposta em 278 s — dentro do limite, que 358,7 s não cabiam.
    limite_oc = TEMPO_MAXIMO_OC_PADRAO_S if tempo_maximo_s is None else float(tempo_maximo_s)
    por_chave_lote = {str(lote_id): (tecido, moldes_qtd) for lote_id, (tecido, moldes_qtd) in grupos.items()}
    custos_por_lote: dict[str, list[float]] = {}
    for chave, (tecido, moldes_qtd) in por_chave_lote.items():
        analise = _analisar_lote(tecido, moldes_qtd)
        if escolhas and chave in escolhas:
            tipo_c, modo_c = escolhas[chave]
            lista = decisor.candidatos(analise, tipo_c, modo_c)
        else:
            lista = decisor.candidatos(analise, tipo_fixo, modo_fixo)
        # O mesmo cálculo serve para o piso daqui e para a ordem de simulação
        # de _decidir_lote — por isso fica guardado, e não é refeito lá.
        custos_por_lote[chave] = _custos_candidatos(tecido, moldes_qtd, limite_cm, lista)
    pisos = {chave: min(custos, default=0.0) for chave, custos in custos_por_lote.items()}
    piso_rapido = sum(pisos.values())
    folga = max(0.0, limite_oc - piso_rapido)
    tempo_comparacao = min(decisor.TEMPO_COMPARACAO_S, folga * FOLHA_COMPARACAO)
    if tempo_comparacao <= 0:
        # Abaixo de 10 s o inteiro arredonda para 0 e o texto mente.
        limite_txt = f"{limite_oc:.0f}" if limite_oc >= 10 else f"{limite_oc:.1f}"
        motivo_prazo = (
            f"o perfil mais barato deste pedido já está em {piso_rapido:.0f} s estimados, "
            f"todo o limite de {limite_txt} s (Configurações > Produção > Tempo limite da "
            f"ordem de corte): não sobrou tempo para comparar"
        )
    else:
        motivo_prazo = f"a comparação passou de {tempo_comparacao:.0f} s"
    prazo = t_decisao + tempo_comparacao

    # Lote mais barato primeiro: o mesmo segundo decide mais lotes, e — o que
    # importa mais — a ordem deixa de depender da velocidade da máquina. Antes
    # o tempo acabava no primeiro lote da lista e o resto ia para o padrão,
    # com o resultado mudando de uma execução para a outra.
    escolhidos: dict[str, tuple[str, str]] = dict(escolhas or {})
    a_decidir = [c for c in por_chave_lote if c not in escolhidos]
    a_decidir.sort(key=lambda c: (pisos[c], c))
    decididos_agora: set[str] = set()
    for chave in a_decidir:
        tecido, moldes_qtd = por_chave_lote[chave]
        if chave not in decisoes:
            decisoes[chave] = _decidir_lote(
                tecido,
                moldes_qtd,
                limite_cm,
                tipo_fixo=tipo_fixo,
                modo_fixo=modo_fixo,
                semente=semente,
                cache=cache,
                prazo=prazo,
                progresso=progresso,
                motivo_prazo=motivo_prazo,
                custos=custos_por_lote[chave],
            )
            decididos_agora.add(chave)
        escolhidos[chave] = (decisoes[chave].tipo, decisoes[chave].modo)

    # O que a comparação deixou no cache e a geração vai reaproveitar é SÓ o
    # candidato vencedor, no perfil Rápido: mesmo lote, mesmo tipo/modo, mesma
    # semente e mesmo limite ⇒ as mesmas chaves de cache. O tempo dos
    # candidatos perdedores não volta — foi gasto de verdade, e pesa no mesmo
    # limite do usuário. Por isso só o DEGRAU de cada risco é cobrado abaixo:
    # o piso Rápido do plano escolhido já foi pago aqui.
    #
    # Só conta o que foi decidido NESTA chamada: no retry a semente muda, o
    # cache não bate mais e o motor roda tudo de novo do zero.
    piso_pago_s = 0.0
    for chave in decididos_agora:
        d = decisoes[chave]
        piso_pago_s += sum(
            c.segundos for c in d.candidatos if c.avaliado and c.erro is None and (c.tipo, c.modo) == (d.tipo, d.modo)
        )
    logger.info(
        "[NESTING] comparação: piso estimado %.0f s, limite %.0f s, orçamento %.0f s, "
        "gasto %.0f s, reaproveitado %.0f s",
        piso_rapido,
        limite_oc,
        tempo_comparacao,
        time.monotonic() - t_decisao,
        piso_pago_s,
    )

    # 2º (AUTOMATICO) distribui o orçamento de tempo entre TODOS os riscos da
    # OC antes de encaixar o primeiro: cada risco começa no perfil Rápido e
    # sobe um degrau (Equilibrado, Máximo) enquanto sobrar tempo, na ordem dos
    # riscos mais pesados. Só aqui se sabe o tamanho de todos — planejar (que é
    # puro e não roda o motor) sai mais barato do que qualquer tentativa de
    # adivinhar, e é o que dá a lista completa de riscos para o orçamento.
    # 3º (abaixo) o laço de geração usa esses perfis; a comparação de enfesto
    # do passo 1º roda sempre no perfil mais barato e alimenta o cache.
    orcamento: Orcamento | None = None
    perfis: dict[str, dict[int, str]] = {}
    if qualidade == QUALIDADE_PADRAO:
        orcamento = Orcamento(
            TEMPO_MAXIMO_OC_PADRAO_S if tempo_maximo_s is None else float(tempo_maximo_s),
            piso_pago_s=piso_pago_s,
        )
        for lote_id, (tecido, moldes_qtd) in grupos.items():
            chave = str(lote_id)
            tipo, modo_lote = escolhidos[chave]
            por_chave, qtd_chave = _quantidades(moldes_qtd)
            for n, (pecas, area) in enumerate(
                _enfestos_do_lote(
                    por_chave,
                    qtd_chave,
                    tecido.max_camadas,
                    tipo=tipo,
                    modo=modo_lote,
                    camadas_pares=tipo == decisor.FACE_A_FACE and _tem_par(moldes_qtd),
                ),
                start=1,
            ):
                orcamento.registrar(
                    (chave, n),
                    pecas=pecas,
                    area_cm2=area,
                    largura_cm=tecido.largura_util_cm,
                    limite_cm=limite_cm,
                )
        atribuicao = orcamento.distribuir()
        for (chave, n), perfil in atribuicao.items():
            perfis.setdefault(chave, {})[n] = perfil
        aviso_orcamento = orcamento.aviso
        if aviso_orcamento:
            avisos.append(aviso_orcamento)

    for lote_id, (tecido, moldes_qtd) in grupos.items():
        chave = str(lote_id)
        tipo, modo_lote = escolhidos[chave]
        decisao = decisoes.get(chave) if not (escolhas and chave in escolhas) else None
        montados, avisos_lote, plano = _gerar_para_tecido(
            pedido,
            tecido,
            moldes_qtd,
            modo_lote,
            ordem_corte_id,
            descricao,
            limite_cm,
            qualidade,
            andamento,
            semente,
            tipo_enfesto=tipo,
            cache=cache,
            perfis=perfis.get(chave),
            orcamento=orcamento,
            chave_lote=chave if orcamento is not None else None,
        )
        if decisao is not None and montados:
            # A decisão do lote vai uma vez só, na primeira mesa dele.
            montados[0].mapa_json = {**montados[0].mapa_json, "decisao_enfesto": decisao.json()}
        encaixes.extend(montados)
        avisos.extend(avisos_lote)
        planos[chave] = plano
    return encaixes, avisos, planos, decisoes


def gerar_de_entradas(
    db: Session,
    pedido: Pedido,
    entradas: list[Entrada],
    *,
    modo: str = decisor.AUTOMATICO,
    tipo_enfesto: str = decisor.AUTOMATICO,
    ordem_corte_id: uuid.UUID | None = None,
    descricao: str | None = None,
    comprimento_max_cm: int = COMPRIMENTO_MAX_PADRAO_CM,
    qualidade: str = QUALIDADE_PADRAO,
    progresso: Progresso | None = None,
    antes_de_gravar: Callable[[list[dict]], None] | None = None,
    tempo_maximo_s: float | None = None,
    organizar_por: str = "COR",
    tolerancia_pct: float | None = None,
) -> dict:
    """Núcleo comum: agrupa as entradas por lote, planeja os enfestos, roda o
    motor v2 e grava tudo numa transação — erro em qualquer lote desfaz tudo
    (inclusive o que o chamador deixou pendente na sessão).

    comprimento_max_cm: limite de cada encaixe (mesa de corte) — risco maior
    é dividido em mesas pelo v2.
    organizar_por: COR (padrão, um grupo por lote, o fluxo de sempre) ou
    PRODUTO (plano de corte por produto, enfesto multicor — ver
    _montar_plano_corte); tolerancia_pct é a do plano (Configurações >
    Produção).
    modo / tipo_enfesto: "AUTOMATICO" (padrão) — o sistema decide o enfesto
    de cada lote (ver _decidir_lote); valor fixo = escolha manual.
    qualidade: ver QUALIDADES — AUTOMATICO distribui o orçamento de tempo da
    ordem de corte entre os riscos (tempo_maximo_s, Configurações >
    Produção); um perfil fixo é a escolha manual do "Avançado".
    Falha ou tempo do motor: UMA nova tentativa automática com outra semente
    e perfil RAPIDO; se falhar de novo, ErroNesting (o job vira ERRO com
    mensagem legível e nada é gravado). Motor indisponível (exe sem
    spyrrow/ortools): ErroNesting com instrução de reinstalar.
    progresso: callback (ver _Andamento); GeracaoCancelada levantada nele
    interrompe sem gravar.
    antes_de_gravar: chamado com as decisões (ver "decisoes" abaixo) depois
    do motor e antes do commit, na mesma transação (a OC marca os encaixes
    anteriores como deletados e grava a decisão do enfesto aqui).

    Returns: {"encaixes": [...resumos], "avisos": [...], "planos": {lote_id: plano},
              "decisoes": [{lote_id, grupo, tecido, produto_nome?, **Decisao.json()}],
              "motor_usado": "v2", "totais": {...}}
    Raises: ValueError se nenhuma entrada tiver quantidade; ErroNesting se o
        motor falhar nas duas tentativas; GeracaoCancelada.
    """
    por_produto = organizar_por == "PRODUTO"
    grupos = _agrupar_produto(entradas) if por_produto else _agrupar_por_lote(entradas)
    if not grupos:
        db.rollback()
        raise ValueError("Nenhuma peça para encaixar: verifique tecidos, moldes e quantidades.")

    if not nesting_v2.DISPONIVEL:
        db.rollback()
        raise ErroNesting("Motor de encaixe não instalado corretamente. Reinstale o SmartCut.")

    tolerancia = plano_corte.TOLERANCIA_PADRAO_PCT if tolerancia_pct is None else float(tolerancia_pct)
    if por_produto:
        # Mesma chamada de _montar_todos; o modo de camadas não se aplica (o
        # plano de corte decide as camadas de cada cor).
        def montar(pedido, grupos, _modo, *resto, **kw):
            kw.pop("decisoes", None)
            return _montar_plano_corte(pedido, grupos, *resto, tolerancia_pct=tolerancia, **kw)
    else:
        montar = _montar_todos
    args = (pedido, grupos, modo, ordem_corte_id, descricao, comprimento_max_cm)
    semente, tentativas = 0, 0
    perfil = qualidade
    cache: dict = {}
    decisoes: dict[str, decisor.Decisao] = {}
    try:
        while True:
            try:
                encaixes, avisos, planos, decisoes = montar(
                    *args,
                    perfil,
                    progresso,
                    semente,
                    tipo_enfesto=tipo_enfesto,
                    cache=cache,
                    decisoes=decisoes,
                    tempo_maximo_s=tempo_maximo_s,
                )
                break
            except GeracaoCancelada:
                raise
            except Exception as exc:
                tentativas += 1
                if tentativas >= 2:
                    raise ErroNesting(str(exc) or type(exc).__name__) from exc
                logger.exception("[NESTING] motor v2 falhou (semente %d) — nova tentativa com perfil RAPIDO", semente)
                perfil, semente = "RAPIDO", semente + 1
        if por_produto:
            # lote_id, lotes, tecido, produto_nome e o plano vêm em Decisao.extra.
            decisoes_out = [{"grupo": k, **d.json()} for k, d in decisoes.items()]
        else:
            nomes = {str(lote_id): tecido.nome for lote_id, (tecido, _) in grupos.items()}
            decisoes_out = [{"lote_id": k, "grupo": k, "tecido": nomes.get(k), **d.json()} for k, d in decisoes.items()]
        if antes_de_gravar is not None:
            antes_de_gravar(decisoes_out)
        if encaixes:
            _gravar(db, encaixes)
    except Exception:
        db.rollback()
        raise

    return {
        "encaixes": [_resumo(e) for e in encaixes],
        "avisos": avisos,
        "planos": planos,
        "decisoes": decisoes_out,
        "motor_usado": "v2",
        "totais": totais(encaixes),
    }


def simular_totais(
    entradas: list[Entrada],
    *,
    escolhas: dict[str, tuple[str, str]],
    comprimento_max_cm: int,
    qualidade: str = "RAPIDO",
    progresso: Progresso | None = None,
    organizar_por: str = "COR",
    tolerancia_pct: float | None = None,
) -> dict:
    """Roda o v2 SEM gravar nada e devolve só os totais (ver totais) — é a
    simulação do alerta de mesa maior. escolhas: {grupo: (tipo_enfesto,
    modo_camadas)} decididos na geração (grupo sem escolha decide de novo);
    organizar_por igual ao da geração, senão as chaves não batem.
    Erro do motor sobe sem nova tentativa."""
    if organizar_por == "PRODUTO":
        encaixes, _, _, _ = _montar_plano_corte(
            None,
            _agrupar_produto(entradas),
            None,
            None,
            comprimento_max_cm,
            qualidade,
            progresso,
            escolhas=escolhas,
            tolerancia_pct=plano_corte.TOLERANCIA_PADRAO_PCT if tolerancia_pct is None else float(tolerancia_pct),
        )
        return totais(encaixes)
    grupos = _agrupar_por_lote(entradas)
    encaixes, _, _, _ = _montar_todos(
        None, grupos, decisor.AUTOMATICO, None, None, comprimento_max_cm, qualidade, progresso, escolhas=escolhas
    )
    return totais(encaixes)


def gerar_encaixe(
    db: Session,
    pedido_id: uuid.UUID,
    comprimento_max_cm: int = COMPRIMENTO_MAX_PADRAO_CM,
    *,
    qualidade: str = QUALIDADE_PADRAO,
    tipo_enfesto: str = decisor.AUTOMATICO,
    modo_camadas: str = decisor.AUTOMATICO,
    progresso: Progresso | None = None,
) -> dict:
    """Encaixe Rápido: gera encaixes para todos os lotes do pedido interno
    (formato legado). O enfesto (tipo e modo de camadas) é decidido pelo
    sistema como na OC — tipo_enfesto/modo_camadas fixos são a escolha
    manual do "Avançado" — e o risco que passar de comprimento_max_cm é
    dividido em mesas.

    qualidade: ver QUALIDADES (AUTOMATICO é o padrão); falha ou tempo do
    motor passam pelo retry automático do gerar_de_entradas.

    Returns:
        {"encaixes": [...resumo de cada Encaixe criado...], "avisos": [...],
         "decisoes": [...decisão do enfesto por lote...], "motor_usado": ...}
        — avisos cobre itens/tamanhos ignorados que não impediram a geração.

    Raises:
        ValueError: se o pedido não existir, não tiver itens, ou se nenhuma
            peça pôde ser agrupada (todas sem tecido/molde válido).
        ErroNesting: se o motor de nesting falhar nas duas tentativas.
    """
    pedido = (
        db.query(Pedido)
        .options(
            selectinload(Pedido.itens).selectinload(ItemPedido.grupo).selectinload(GrupoMolde.moldes),
            selectinload(Pedido.itens)
            .selectinload(ItemPedido.lote)
            .selectinload(LoteTecido.cor)
            .selectinload(CorTecido.modelo),
        )
        .filter(Pedido.id == pedido_id)
        .first()
    )

    if not pedido:
        raise ValueError("Pedido não encontrado.")

    if not pedido.itens:
        raise ValueError("O pedido não possui itens cadastrados.")

    entradas, avisos = montar_pares_legado(pedido)
    for aviso in avisos:
        logger.info("[NESTING] %s", aviso)

    if not entradas:
        raise ValueError(
            "Nenhuma peça foi vinculada a um tecido. Selecione um tecido para cada peça antes de gerar o encaixe."
        )

    resultado = gerar_de_entradas(
        db,
        pedido,
        entradas,
        modo=modo_camadas,
        tipo_enfesto=tipo_enfesto,
        descricao=pedido.observacoes_internas,
        comprimento_max_cm=comprimento_max_cm,
        qualidade=qualidade,
        progresso=progresso,
        tempo_maximo_s=float(config_producao(db)["tempo_maximo_oc_s"]),
    )
    return {
        "encaixes": resultado["encaixes"],
        "avisos": avisos + resultado["avisos"],
        "decisoes": resultado["decisoes"],
        "motor_usado": resultado["motor_usado"],
    }
