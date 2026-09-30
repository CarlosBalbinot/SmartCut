"""custo.py — o preço em TEMPO de um risco de corte, e o perfil que cabe no
orçamento da Ordem de Corte.

Por que tempo e não tecido
--------------------------
O spyrrow trabalha em segundos INTEIROS com piso de 1 s por chamada
(nesting_v2/encaixador.py). O custo de um risco é, essencialmente, o NÚMERO DE
CHAMADAS — e é por isso que o mesmo risco sai com 5,84 m no perfil Rápido e com
5,84 m no Máximo: 7× o tempo pelo mesmo tecido. Medido no motor (OC-0004,
LEGGING FLARE, MAXXI 150 cm, mesa de 150 cm):

    risco                      camadas  peças  mesas  chamadas  Rápido  Equilibrado  Máximo
    P1 M2 G2 GG1                 15      30      5      39      45,7 s    116,5 s    318,3 s
    P1 G3 GG1                    3      25      5     ~20      26,1 s     ~68 s    ~184 s
    G1 GG2                       1      15      3     ~11      14,1 s     ~37 s    ~100 s
    P1 M1 G1 GG1 (CANELADO)     10      50     10     ~80      87,6 s    ~223 s    ~609 s
    M1 G1 (1 camada)             1       5      2      ~4       8,0 s     ~21 s     ~56 s
    P1 M1 (1 camada)             1       5      2      ~4       8,7 s     ~23 s     ~61 s

Duas constantes fecham o perfil Rápido — `SEGUNDOS_PECA` e `SEGUNDOS_MESA` —
e os multiplicadores dos outros perfis saem das três primeiras linhas
(2,55× e 6,97×). O estimador é deliberadamente PESSIMISTA: no conjunto medido
ele nunca subestima, e errar para o lado caro é o que mantém a geração dentro
do prazo. Ele serve para distribuir orçamento, não para escolher plano.

O número de mesas sai da ÁREA (o aproveitamento medido no LEGGING FLARE fica
entre 0,49 e 0,59; 0,55 é o meio da faixa) — não dá para prever quantas mesas
o spyrrow vai abrir sem rodar, e a área basta para orçamento.

O orçamento
----------
O perfil RÁPIDO é o piso: é o mais barato que existe para qualquer pedido. E ele
já foi pago antes do orçamento existir — a comparação de enfesto roda todos os
candidatos no perfil mais barato para escolher o modo de camadas, e a geração
definitiva reaproveita o que ficou no cache. Por isso o que o orçamento
distribui é o DEGRAU de cada risco, e o tempo da comparação sai da mesma conta
do usuário (`piso_pago_s`).

SOBRE O QUE SOBRA, `Orcamento` SOBE UM DEGRAU POR VEZ, sempre no risco mais
pesado ainda no piso — o que tem mais peças, e portanto mais tecido em jogo
para o empacotamento melhorar. Um degrau só por vez, e sempre no mais pesado, é
o que impede o desvio que a ordem ingênua por "custo do degrau" produz: um
risco de 5 peças subindo a Máximo (barato, e quase sem nada a ganhar) com o
tempo que o risco de 50 peças usaria para um degrau.

Quando nem o piso cabe no que sobrou do limite, sobra um aviso — não existe
perfil mais barato.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, field

# Área das peças / área da faixa. Medido no LEGGING FLARE: 0,49 a 0,59.
DENSIDADE = 0.55

# Segundos por peça física e por mesa no perfil RÁPIDO (ver tabela do módulo).
SEGUNDOS_PECA = 1.15
SEGUNDOS_MESA = 2.0

# Quanto cada perfil custa em relação ao Rápido.
MULTIPLICADORES: dict[str, float] = {"RAPIDO": 1.0, "EQUILIBRADO": 2.55, "MAXIMO": 6.97}

# Do mais barato ao mais caro — a ordem em que o orçamento sobe um degrau.
PERFIS: tuple[str, ...] = ("RAPIDO", "EQUILIBRADO", "MAXIMO")

# Teto de segurança do orçamento: a sobra estimada nunca passa disso (o
# estimador é pessimista, mas não há por que apostar o dobro).
FOLGA_SEGURANCA = 0.9


def estimar_mesas(area_cm2: float, largura_cm: float, limite_cm: int) -> int:
    """Mesas que a área das peças ocupa, com o aproveitamento DENSIDADE."""
    if largura_cm <= 0 or area_cm2 <= 0:
        return 1
    comprimento_cm = area_cm2 / (largura_cm * DENSIDADE)
    return max(1, -(-int(comprimento_cm) // max(1, limite_cm)))


def estimar_segundos(
    pecas: int,
    area_cm2: float,
    largura_cm: float,
    limite_cm: int,
    perfil: str = "RAPIDO",
) -> float:
    """Segundos que o motor deve levar neste risco, com este perfil.

    `pecas` conta as peças FÍSICAS do risco (conjuntos × multiplicador do
    tipo_corte) e `area_cm2` a área delas — os dois saem das linhas de entrada
    do motor, sem rodar nada.
    """
    mesas = estimar_mesas(area_cm2, largura_cm, limite_cm)
    return (max(0, pecas) * SEGUNDOS_PECA + mesas * SEGUNDOS_MESA) * MULTIPLICADORES.get(perfil, 1.0)


@dataclass
class _Risco:
    chave: Hashable
    pecas: int
    area_cm2: float
    largura_cm: float
    limite_cm: int
    mesas: int
    segundos_rapido: float
    perfil: str = "RAPIDO"


@dataclass
class Orcamento:
    """Perfil de tempo de cada risco de uma geração.

    `registrar` anota o risco e `distribuir` devolve {chave: perfil}: todos
    começam no Rápido e sobem um degrau por vez, na fila dos riscos mais
    pesados, enquanto sobrar tempo.

    O PISO (Rápido) já foi pago antes de o orçamento existir — a comparação de
    enfesto roda todos os candidatos no perfil mais barato para escolher o
    modo de camadas, e a geração reaproveita o que ficou no cache. Por isso o
    que o orçamento distribui é o DEGRAU de cada risco, e não o preço inteiro:
    `piso_pago_s` é esse tempo já gasto, que sai da mesma conta do usuário.

    `aviso` é o caso em que o tempo restante não compra nem o piso dos riscos
    que faltam — a geração vai passar do prazo e não há perfil mais barato.
    """

    limite_s: float
    piso_pago_s: float = 0.0
    riscos: list[_Risco] = field(default_factory=list)
    sobra_s: float = 0.0
    distribuido: bool = False

    def registrar(
        self,
        chave: Hashable,
        *,
        pecas: int,
        area_cm2: float,
        largura_cm: float,
        limite_cm: int,
    ) -> None:
        self.riscos.append(
            _Risco(
                chave=chave,
                pecas=pecas,
                area_cm2=area_cm2,
                largura_cm=largura_cm,
                limite_cm=limite_cm,
                mesas=estimar_mesas(area_cm2, largura_cm, limite_cm),
                segundos_rapido=estimar_segundos(pecas, area_cm2, largura_cm, limite_cm),
            )
        )

    @property
    def total_rapido_s(self) -> float:
        """Custo estimado dos riscos no piso (o que a comparação já pagou)."""
        return sum(r.segundos_rapido for r in self.riscos)

    @property
    def disponivel_s(self) -> float:
        """Quanto do limite ainda resta depois do piso já pago."""
        return max(0.0, self.limite_s - self.piso_pago_s)

    @property
    def aviso(self) -> str | None:
        """O tempo que resta não compra nem o piso dos riscos pendentes."""
        if not self.riscos:
            return None
        if self.disponivel_s >= self.total_rapido_s:
            return None
        # Abaixo de 1 s o arredondamento diria "já levou 0 s", que é mentira.
        gasto = f"A comparação de enfestos já levou {self.piso_pago_s:.0f} s e " if self.piso_pago_s >= 1 else ""
        return (
            f"{gasto}o encaixe no perfil Rápido está em {self.total_rapido_s:.0f} s estimados, "
            f"acima dos {self.disponivel_s:.0f} s que sobram de {self.limite_s:.0f} s "
            "(Configurações > Produção > Tempo limite da ordem de corte). O perfil mais barato "
            "já estoura o limite; a geração vai demorar mais que ele. A estimativa é o teto, "
            "não a média — o motor costuma sair mais rápido, mas não se pode contar com isso."
        )

    def distribuir(self) -> dict[Hashable, str]:
        """{chave: perfil} — a sobra sobe um degrau no risco mais pesado que
        ainda está no piso, enquanto o prazo permitir."""
        if not self.distribuido:
            self.distribuido = True
            self.sobra_s = self.disponivel_s * FOLGA_SEGURANCA - self.total_rapido_s
            # Mais peças primeiro: é o risco com mais tecido em jogo, e o
            # empacotamento é o que o perfil melhora. Empates vão para o que
            # mais tempo consome, que é o mesmo critério do resto.
            for risco in sorted(self.riscos, key=lambda r: (-r.pecas, -r.segundos_rapido)):
                self._sobe_um_degrau(risco)
        return {r.chave: r.perfil for r in self.riscos}

    def _sobe_um_degrau(self, risco: _Risco) -> None:
        """Sobe UM degrau (Rápido → Equilibrado → Máximo) se ele couber na
        sobra. Quem não coube fica no piso — e o próximo risco mais pesado
        ainda tem chance com o tempo que sobrar."""
        i = PERFIS.index(risco.perfil)
        if i + 1 >= len(PERFIS):
            return
        atual_s = estimar_segundos(risco.pecas, risco.area_cm2, risco.largura_cm, risco.limite_cm, risco.perfil)
        custo = estimar_segundos(risco.pecas, risco.area_cm2, risco.largura_cm, risco.limite_cm, PERFIS[i + 1])
        if custo - atual_s > self.sobra_s:
            return
        self.sobra_s -= custo - atual_s
        risco.perfil = PERFIS[i + 1]

    def detalhe(self, chave: Hashable) -> dict:
        """O que gravar no mapa_json do risco: perfil, o que ele custou e por
        que ficou nele (documento no retorno, como era a regra das peças)."""
        risco = next((r for r in self.riscos if r.chave == chave), None)
        if risco is None:
            return {}
        segundos = estimar_segundos(risco.pecas, risco.area_cm2, risco.largura_cm, risco.limite_cm, risco.perfil)
        degrau = segundos - risco.segundos_rapido
        return {
            "perfil": risco.perfil,
            "pecas": risco.pecas,
            "mesas_estimadas": risco.mesas,
            "segundos_estimados": round(segundos, 1),
            "orcamento_s": round(self.limite_s),
            "piso_pago_s": round(self.piso_pago_s),
            "regra": (
                f"perfil por tempo: {risco.perfil} · {segundos:.0f} s estimados para este risco, "
                f"dentro de {self.limite_s:.0f} s para a ordem de corte"
                + (
                    f" (degrau de {degrau:.0f} s sobre o piso Rápido, que a comparação já pagou)"
                    if degrau > 0.5
                    else " (piso Rápido)"
                )
            ),
        }
