"""decisor.py — o sistema escolhe o tipo de enfesto e o modo de camadas.

O usuário não escolhe como estender: para cada lote de tecido o sistema
avalia as alternativas válidas, fica com a melhor e explica o porquê. Aqui
fica a parte PURA da decisão (sem banco e sem motor); quem roda as
simulações é services/nesting_service.py (_decidir_lote).

Tipos de enfesto
----------------
  MESMA_FACE ("Enfesto simples") — todas as camadas com o lado direito para
      cima; corta no fim da mesa e volta ao início. Peça `par` entra DUAS
      vezes no desenho, a 2ª espelhada (geometria.espelha_segunda_copia).
  FACE_A_FACE ("Enfesto duplo") — estende indo e voltando, virando o tecido a
      cada camada. Peça `par` entra duas vezes SEM espelho: a alternância
      das camadas faz a direita e a esquerda — por isso exige camadas pares
      quando há `par` (plano_enfesto, camadas_pares=True).
  `par_sem_espelho` são duas peças IGUAIS, nunca espelhadas, nos dois tipos
  de enfesto; não pede camadas pares.

Nomes: os códigos MESMA_FACE e FACE_A_FACE são internos e não mudam; quem vê
a tela e o formulário de corte lê "enfesto simples" e "enfesto duplo", que é
como a produção nomeia na sala de corte.

Enfesto duplo é inválido quando:
  * o tecido tem direção (estampa ou pelo) — não pode ser virado;
  * há peça ÚNICA assimétrica — metade das camadas a cortaria espelhada;
  * há `par_sem_espelho` assimétrico — pela mesma razão: as duas peças
    iguais sairiam viradas em metade das camadas;
  * o lote tem 1 camada (regra da produção: 1 camada é sempre enfesto simples)
    ou o tecido aceita no máximo 1 camada.
Todas as razões que valem entram no motivo (com todas as peças envolvidas) e
os códigos delas viram a `regra` quando foi o descarte que decidiu
(RAZOES_INVALIDA).

Critério (escolher)
-------------------
  1. menor consumo de tecido: metros × camadas, todas as mesas;
  2. empate técnico (diferença < EMPATE_PCT): candidato sem sobra antes de
     um com sobra; depois MENOS MESAS; só entre os que empatam também em
     mesas vale o tipo preferido pelas regras da produção — produto de
     dupla camada (forrado, pelo cadastro) → enfesto duplo; 2 ou 3 camadas
     → enfesto simples; senão enfesto duplo (mais rápido de estender);
     depois menos camadas;
  3. sobra de peças só vence se for o menor consumo fora do empate.

"Dupla camada" é cadastro (produtos.dupla_camada), não inferência: peça em
par (costas direita e esquerda) existe em quase toda legging e não diz nada
sobre o tecido.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field

from shapely.geometry import Polygon

from services.nesting_v2.geometria import eixo_do_fio, espelhar, normalizar

MESMA_FACE = "MESMA_FACE"
FACE_A_FACE = "FACE_A_FACE"
TIPOS = (MESMA_FACE, FACE_A_FACE)
AUTOMATICO = "AUTOMATICO"
NOME_TIPO = {MESMA_FACE: "Enfesto simples", FACE_A_FACE: "Enfesto duplo"}
# PLANO_CORTE: a OC organizada por produto — as camadas de cada cor saem do
# plano de corte (services/planejamento/plano_corte.py), não de um modo.
PLANO_CORTE = "PLANO_CORTE"
NOME_MODO = {"SEM_SOBRA": "sem sobra", "MENOS_ENFESTOS": "menos enfestos", PLANO_CORTE: "plano por produto"}

PAR = "PAR"
UNICO_SIMETRICO = "UNICO_SIMETRICO"
UNICO_ASSIMETRICO = "UNICO_ASSIMETRICO"
# par_sem_espelho: duas peças iguais, nunca espelhadas.
PAR_SEM_ESPELHO_SIMETRICO = "PAR_SEM_ESPELHO_SIMETRICO"
PAR_SEM_ESPELHO_ASSIMETRICO = "PAR_SEM_ESPELHO_ASSIMETRICO"

# Razões que invalidam o enfesto duplo (código → vai para a `regra`).
TECIDO_COM_DIRECAO = "TECIDO_COM_DIRECAO"
PECA_ASSIMETRICA = "PECA_ASSIMETRICA"
PAR_SEM_ESPELHO_ASSIM = "PAR_SEM_ESPELHO_ASSIMETRICO"
UMA_CAMADA = "UMA_CAMADA"
TECIDO_UMA_CAMADA = "TECIDO_UMA_CAMADA"
RAZOES_INVALIDA = (TECIDO_COM_DIRECAO, PECA_ASSIMETRICA, PAR_SEM_ESPELHO_ASSIM, UMA_CAMADA, TECIDO_UMA_CAMADA)

# Simetria: diferença simétrica entre a peça e o espelho dela no eixo do fio,
# dividida pelo perímetro — a "largura média" do desvio, em cm.
TOLERANCIA_SIMETRIA_CM = 0.3
# Diferença de consumo abaixo da qual dois candidatos empatam (%).
EMPATE_PCT = 1.0
# Teto da comparação (simulações RÁPIDO dos candidatos, todos os lotes).
# É só um TETO: o orçamento de verdade é uma fatia do limite da Ordem de Corte
# (nesting_service.FOLHA_COMPARACAO), porque a comparação roda o motor e esse
# tempo sai da mesma conta do usuário. Sem folga nenhuma, a comparação não roda
# — e todos os lotes vão para o padrão seguro, registrado no motivo.
TEMPO_COMPARACAO_S = 180.0


# ── Peças ────────────────────────────────────────────────────────────────────


def desvio_simetria_cm(poligono: list[list[float]], rotacoes: Iterable[float]) -> float:
    """Largura média (cm) do que muda quando a peça é espelhada no eixo do
    fio. 0 = simétrica. Geometria inválida → infinito (conta como
    assimétrica: na dúvida, não se vira a peça)."""
    try:
        base = normalizar(poligono)
        original = Polygon(base).buffer(0)
        virada = Polygon(espelhar(base, eixo_do_fio(tuple(float(r) for r in rotacoes)))).buffer(0)
        if original.is_empty or original.length <= 0:
            return float("inf")
        return original.symmetric_difference(virada).area / original.length
    except Exception:  # noqa: BLE001
        return float("inf")


def classificar(
    poligono: list[list[float]],
    rotacoes: Iterable[float],
    tipo_corte: str | None,
    tolerancia_cm: float = TOLERANCIA_SIMETRIA_CM,
) -> str:
    """PAR (par, 2 espelhadas); PAR_SEM_ESPELHO_SIMETRICO/ASSIMETRICO
    (par_sem_espelho, 2 iguais); UNICO_SIMETRICO ou UNICO_ASSIMETRICO."""
    tipo = tipo_corte or "simples"
    if tipo == "par":
        return PAR
    simetrica = desvio_simetria_cm(poligono, rotacoes) <= tolerancia_cm
    if tipo == "par_sem_espelho":
        return PAR_SEM_ESPELHO_SIMETRICO if simetrica else PAR_SEM_ESPELHO_ASSIMETRICO
    return UNICO_SIMETRICO if simetrica else UNICO_ASSIMETRICO


@dataclass
class PecaAnalise:
    """O que o decisor precisa de um molde."""

    nome: str
    poligono: list[list[float]]
    rotacoes: tuple[float, ...]
    tipo_corte: str


@dataclass
class Analise:
    """Resultado da análise das peças de um lote."""

    classes: dict[str, str]
    tem_par: bool
    assimetricas: list[str]
    tem_direcao: bool
    camadas_naturais: int
    max_camadas: int
    face_a_face_valida: bool
    # Cadastro do produto pai (produtos.dupla_camada): o produto é de dupla
    # camada / forrado. É o ÚNICO jeito de o lote ser "dupla" — peças em par
    # (costas direita e esquerda) existem em quase toda legging e não dizem
    # nada sobre o tecido.
    dupla_camada: bool = False
    motivo_invalida: str | None = None
    # par_sem_espelho assimétricos (invalidam o enfesto duplo, como a peça
    # única assimétrica).
    pares_assimetricos: list[str] = field(default_factory=list)
    # [(código, texto)] de TODAS as razões que invalidam o enfesto duplo, na
    # ordem de RAZOES_INVALIDA; motivo_invalida é a junção dos textos.
    razoes_invalida: list[tuple[str, str]] = field(default_factory=list)

    @property
    def regra_invalida(self) -> str | None:
        """Os códigos das razões ("PECA_ASSIMETRICA+UMA_CAMADA")."""
        return "+".join(c for c, _ in self.razoes_invalida) or None

    @property
    def dupla(self) -> bool:
        """Produto de dupla camada (forrado), pelo cadastro. A produção
        prefere enfesto duplo para cortar as duas camadas de uma vez."""
        return self.dupla_camada


def analisar(
    pecas: dict[str, PecaAnalise],
    *,
    tem_direcao: bool,
    camadas_naturais: list[int],
    max_camadas: int,
    dupla_camada: bool = False,
) -> Analise:
    """Classifica os moldes e diz se enfesto duplo vale para o lote.

    camadas_naturais: camadas de cada enfesto do plano enfesto simples + sem
    sobra (sem arredondar para par) — é o "quantas camadas este pedido tem"
    das regras da produção.

    dupla_camada: vem do cadastro do produto pai (ver Analise.dupla_camada)."""
    classes = {mid: classificar(p.poligono, p.rotacoes, p.tipo_corte) for mid, p in pecas.items()}
    assimetricas = sorted({pecas[mid].nome for mid, c in classes.items() if c == UNICO_ASSIMETRICO})
    pares_assimetricos = sorted({pecas[mid].nome for mid, c in classes.items() if c == PAR_SEM_ESPELHO_ASSIMETRICO})
    maior = max(camadas_naturais, default=0)
    razoes: list[tuple[str, str]] = []
    if tem_direcao:
        razoes.append((TECIDO_COM_DIRECAO, "tecido com direção (estampa ou pelo): não pode ser virado"))
    if assimetricas:
        razoes.append(
            (
                PECA_ASSIMETRICA,
                f"peça única assimétrica ({', '.join(assimetricas)}): sairia espelhada em metade das camadas",
            )
        )
    if pares_assimetricos:
        razoes.append(
            (
                PAR_SEM_ESPELHO_ASSIM,
                f"par sem espelho assimétrico ({', '.join(pares_assimetricos)}): "
                "as duas peças iguais sairiam espelhadas em metade das camadas",
            )
        )
    if maior <= 1:
        razoes.append((UMA_CAMADA, "1 camada: regra da produção, sempre enfesto simples"))
    if max_camadas < 2:
        razoes.append((TECIDO_UMA_CAMADA, "o tecido aceita no máximo 1 camada"))
    motivo = "; ".join(texto for _, texto in razoes) or None
    return Analise(
        classes=classes,
        tem_par=PAR in classes.values(),
        assimetricas=assimetricas,
        tem_direcao=tem_direcao,
        camadas_naturais=maior,
        max_camadas=max_camadas,
        face_a_face_valida=motivo is None,
        dupla_camada=dupla_camada,
        motivo_invalida=motivo,
        pares_assimetricos=pares_assimetricos,
        razoes_invalida=razoes,
    )


# ── Escolha ──────────────────────────────────────────────────────────────────


@dataclass
class Candidato:
    """Uma forma de enfesto avaliada (simulação rápida, sem gravar)."""

    tipo: str
    modo: str
    metros: float = 0.0
    mesas: int = 0
    enfestos: int = 0
    camadas: int = 0
    sobra: int = 0
    segundos: float = 0.0
    erro: str | None = None
    avaliado: bool = True

    @property
    def rotulo(self) -> str:
        return f"{NOME_TIPO[self.tipo]}, {NOME_MODO.get(self.modo, self.modo)}"

    def json(self) -> dict:
        return {**asdict(self), "rotulo": self.rotulo, "tipo_nome": NOME_TIPO[self.tipo]}


def candidatos(analise: Analise, tipo_fixo: str | None = None, modo_fixo: str | None = None) -> list[Candidato]:
    """{enfesto simples, enfesto duplo se válido} × {sem sobra, menos
    enfestos} — enfesto simples + sem sobra primeiro (é o padrão seguro,
    avaliado antes para estar pronto se o tempo acabar). Escolha manual do
    "Avançado" fixa uma das dimensões (ou as duas)."""
    tipos = [MESMA_FACE] + ([FACE_A_FACE] if analise.face_a_face_valida else [])
    if tipo_fixo in TIPOS:
        tipos = [tipo_fixo] if tipo_fixo in tipos else [MESMA_FACE]
    modos = ["SEM_SOBRA", "MENOS_ENFESTOS"]
    if modo_fixo in modos:
        modos = [modo_fixo]
    return [Candidato(tipo=t, modo=m) for t in tipos for m in modos]


@dataclass
class Decisao:
    """O que foi decidido para um lote — vai para decisao_enfesto."""

    tipo: str
    modo: str
    motivo: str
    regra: str
    candidatos: list[Candidato] = field(default_factory=list)
    face_a_face_valida: bool = True
    motivo_face_a_face: str | None = None
    classes: dict[str, str] = field(default_factory=dict)
    # Produto de dupla camada (forrado) pelo cadastro — fica gravado para dar
    # para conferir depois por que o enfesto duplo venceu um empate.
    dupla_camada: bool = False
    tempo_esgotado: bool = False
    manual: bool = False
    segundos: float = 0.0
    # O que o chamador acrescenta à decisão gravada (plano de corte: lotes,
    # tecido, produto e o plano). Entra por último no json.
    extra: dict = field(default_factory=dict)

    def json(self) -> dict:
        return {
            "tipo_enfesto": self.tipo,
            "tipo_nome": NOME_TIPO[self.tipo],
            "modo_camadas": self.modo,
            "motivo": self.motivo,
            "regra": self.regra,
            "face_a_face_valida": self.face_a_face_valida,
            "motivo_face_a_face": self.motivo_face_a_face,
            "dupla_camada": self.dupla_camada,
            "tempo_esgotado": self.tempo_esgotado,
            "manual": self.manual,
            "segundos": round(self.segundos, 1),
            "classes": self.classes,
            "candidatos": [c.json() for c in self.candidatos],
            **self.extra,
        }


def _m(valor: float) -> str:
    return f"{valor:.2f} m".replace(".", ",")


def _pct(valor: float) -> str:
    return f"{valor:.1f}%".replace(".", ",")


def _mesmo_plano(a: Candidato, b: Candidato) -> bool:
    """Mesmo tipo e o mesmo resultado (ex.: sem sobra e menos enfestos quando
    todas as quantidades são iguais) — não é empate, é a mesma coisa."""
    return a.tipo == b.tipo and (a.metros, a.mesas, a.camadas, a.sobra) == (b.metros, b.mesas, b.camadas, b.sobra)


def _preferencia(analise: Analise) -> tuple[str, str, str]:
    """(tipo preferido no empate, regra, frase) pelas regras da produção."""
    if analise.dupla:
        return FACE_A_FACE, "PRODUTO_DUPLA", "produto de dupla camada (forrado) prefere enfesto duplo"
    if 2 <= analise.camadas_naturais <= 3:
        return MESMA_FACE, "POUCAS_CAMADAS", f"{analise.camadas_naturais} camadas: prefere enfesto simples"
    return FACE_A_FACE, "MAIS_RAPIDO", "enfesto duplo é mais rápido de estender"


def escolher(lista: list[Candidato], analise: Analise) -> tuple[Candidato, str, str]:
    """(vencedor, motivo em texto, regra que pesou). `lista` já avaliada;
    candidatos com erro ou não avaliados ficam de fora."""
    validos = [c for c in lista if c.avaliado and c.erro is None]
    if not validos:
        raise ValueError("nenhuma forma de enfesto pôde ser avaliada")
    menor = min(c.metros for c in validos)
    limite = menor * (1 + EMPATE_PCT / 100) if menor > 0 else 0.0
    empate = [c for c in validos if c.metros <= limite + 1e-9]
    notas: list[str] = []

    sem_sobra = [c for c in empate if c.sobra == 0]
    if sem_sobra and len(sem_sobra) < len(empate):
        empate = sem_sobra
        notas.append("sem sobra de peças")

    regra = "MENOR_CONSUMO"
    # Mesas antes das regras da produção: a preferência de tipo só desempata
    # planos com o MESMO número de mesas.
    menos_mesas = min(c.mesas for c in empate)
    if any(c.mesas > menos_mesas for c in empate):
        empate = [c for c in empate if c.mesas == menos_mesas]
        regra = "MENOS_MESAS"
        notas.append(f"menos mesas ({menos_mesas})")
    tipos = {c.tipo for c in empate}
    if len(tipos) > 1:
        preferido, regra, frase = _preferencia(analise)
        empate = [c for c in empate if c.tipo == preferido]
        notas.append(frase)

    vencedor = min(empate, key=lambda c: (c.mesas, c.camadas, c.metros))
    outros = [c for c in validos if c is not vencedor]
    texto = f"{vencedor.rotulo}: {_m(vencedor.metros)} em {vencedor.mesas} mesa{'s' if vencedor.mesas != 1 else ''}"
    if vencedor.sobra:
        texto += f" (sobra de {vencedor.sobra} peça{'s' if vencedor.sobra != 1 else ''})"
    if not outros:
        texto += "."
    elif len(empate) == 1 and all(c.metros > limite + 1e-9 for c in outros):
        melhor_outro = min(outros, key=lambda c: c.metros)
        dif = (melhor_outro.metros - vencedor.metros) / vencedor.metros * 100 if vencedor.metros else 0.0
        texto += f", o menor consumo ({melhor_outro.rotulo}: {_m(melhor_outro.metros)}, +{_pct(dif)})."
    elif all(_mesmo_plano(c, vencedor) for c in outros):
        nomes = ", ".join(c.rotulo.lower() for c in outros)
        texto += f"; {nomes} dá o mesmo resultado."
    else:
        rivais = [c for c in outros if c.metros <= limite + 1e-9 and not _mesmo_plano(c, vencedor)]
        comparado = min(rivais or outros, key=lambda c: c.metros)
        texto += (
            f"; empate técnico com {comparado.rotulo} ({_m(comparado.metros)}, diferença < {EMPATE_PCT:g}%)"
            + (f" — {'; '.join(notas)}" if notas else "")
            + "."
        )
    if not analise.face_a_face_valida and analise.motivo_invalida:
        texto += f" Enfesto duplo descartado: {analise.motivo_invalida}."
        # Sem desempate pelas regras da produção, quem decidiu foi o descarte
        # do enfesto duplo — a regra diz por quê (todas as razões).
        if regra == "MENOR_CONSUMO":
            regra = analise.regra_invalida or regra
    return vencedor, texto, regra


def decisao_padrao_seguro(
    analise: Analise, lista: list[Candidato], motivo: str, tipo: str = MESMA_FACE, modo: str = "SEM_SOBRA"
) -> Decisao:
    """Tempo da comparação esgotado (ou nenhuma simulação concluída): enfesto
    simples + sem sobra (ou o que o "Avançado" fixou), com o porquê no motivo."""
    rotulo = Candidato(tipo=tipo, modo=modo).rotulo
    return Decisao(
        tipo=tipo,
        modo=modo,
        motivo=f"{rotulo} (padrão seguro): {motivo}.",
        regra="PADRAO_SEGURO",
        candidatos=lista,
        face_a_face_valida=analise.face_a_face_valida,
        motivo_face_a_face=analise.motivo_invalida,
        classes=analise.classes,
        dupla_camada=analise.dupla_camada,
        tempo_esgotado=True,
    )
