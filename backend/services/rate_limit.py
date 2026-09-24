"""Proteção contra força bruta nos logins (item 1.3).

Limitação 100% em memória (sem infra externa), por **usuário+IP** e por **IP**:
- após N falhas consecutivas dentro da janela, o par entra em bloqueio
  temporário com cooldown progressivo (15 min → 30 min → … até 2 h);
- login bem-sucedido zera os contadores;
- mensagem de bloqueio é genérica (não revela se o usuário existe).

Limitação documentada: os bloqueios são **voláteis** — reiniciar o processo
do backend zera tudo. Não há persistência de dados sensíveis, apenas
timestamps de tentativas.
"""
import threading
import time

MAX_TENTATIVAS = 5                 # falhas consecutivas (na janela) antes de bloquear
JANELA_FALHAS_S = 30 * 60          # considera apenas falhas desta janela
COOLDOWN_INICIAL_S = 15 * 60       # 15 minutos
COOLDOWN_MAX_S = 2 * 60 * 60       # 2 horas
CAP_CHAVES = 25_000                # trava de memória (número de chaves monitoradas)

_LOCK = threading.Lock()
_FALHAS: dict[str, list[float]] = {}    # chave -> timestamps (time.monotonic) das falhas
_BLOQUEIO_ATE: dict[str, float] = {}    # chave -> monotonic até quando bloqueada
_COOLDOWN_NIVEL: dict[str, int] = {}    # chave -> multiplicador de cooldown (progressivo)


def _chaves(identificador: str, ip: str) -> tuple[str, ...]:
    """Chaves monitoradas: usuário+IP (bloqueia força bruta direcionada) e
    IP puro (bloqueia varredura de vários usuários a partir de um IP)."""
    chaves = {f"{identificador or ''}|{ip}", f"ip:{ip}"}
    return tuple(chaves)


def _limpar(chave: str, agora: float) -> None:
    """Remove o que já não vale: falhas fora da janela e bloqueios expirados.

    Falhas dentro da janela são mantidas (é o que acumula para o bloqueio);
    bloqueio ainda ativo (deadline futuro) também é preservado.
    """
    falhas = _FALHAS.get(chave)
    if falhas:
        falhas[:] = [t for t in falhas if agora - t <= JANELA_FALHAS_S]
        if not falhas:
            _FALHAS.pop(chave, None)
    ate = _BLOQUEIO_ATE.get(chave, 0)
    if ate and ate <= agora:
        _BLOQUEIO_ATE.pop(chave, None)
        _FALHAS.pop(chave, None)
        _COOLDOWN_NIVEL.pop(chave, None)


def _poda_memoria(agora: float) -> None:
    if len(_FALHAS) + len(_BLOQUEIO_ATE) > CAP_CHAVES:
        for chave in list(_FALHAS) + list(_BLOQUEIO_ATE):
            _limpar(chave, agora)


def verificar_bloqueio(identificador: str, ip: str) -> float:
    """Segundos restantes de bloqueio para a chave (0 = liberado)."""
    agora = time.monotonic()
    with _LOCK:
        maior = 0.0
        for chave in _chaves(identificador, ip):
            ate = _BLOQUEIO_ATE.get(chave, 0)
            if ate > agora:
                maior = max(maior, ate - agora)
        return maior


def registrar_falha(identificador: str, ip: str) -> float:
    """Registra uma falha e aplica bloqueio temporário/progressivo.

    - 5 falhas consecutivas → bloqueio de 15 min.
    - enquanto bloqueado, cada tentativa extra estende o bloqueio com
      cooldown crescente (15/30/45 … até 2 h).
    Retorna os segundos de cooldown aplicados agora (0 = abaixo do limite).
    """
    agora = time.monotonic()
    with _LOCK:
        _poda_memoria(agora)
        cooldown_aplicado = 0.0
        for chave in _chaves(identificador, ip):
            _limpar(chave, agora)
            ate_atual = _BLOQUEIO_ATE.get(chave, 0)
            if ate_atual > agora:
                # Já bloqueado: cada tentativa extra estende o bloqueio
                # (atraso progressivo), até o teto.
                nivel = _COOLDOWN_NIVEL.get(chave, 1)
                cooldown = min(COOLDOWN_INICIAL_S * nivel, COOLDOWN_MAX_S)
                _BLOQUEIO_ATE[chave] = ate_atual + cooldown
                _COOLDOWN_NIVEL[chave] = min(
                    nivel + 1, int(COOLDOWN_MAX_S // COOLDOWN_INICIAL_S)
                )
                cooldown_aplicado = max(cooldown_aplicado, cooldown)
                continue

            falhas = _FALHAS.setdefault(chave, [])
            falhas.append(agora)
            if len(falhas) >= MAX_TENTATIVAS:
                cooldown = COOLDOWN_INICIAL_S
                _BLOQUEIO_ATE[chave] = agora + cooldown
                _FALHAS[chave] = []
                _COOLDOWN_NIVEL[chave] = 2  # próxima extensão vale o dobro
                cooldown_aplicado = max(cooldown_aplicado, cooldown)
        return cooldown_aplicado


def registrar_sucesso(identificador: str, ip: str) -> None:
    """Zera contadores, bloqueios e nível de cooldown após login com sucesso."""
    with _LOCK:
        for chave in _chaves(identificador, ip):
            _FALHAS.pop(chave, None)
            _BLOQUEIO_ATE.pop(chave, None)
            _COOLDOWN_NIVEL.pop(chave, None)