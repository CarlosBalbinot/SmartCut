"""nesting_jobs.py — geração de encaixes em segundo plano (M2a).

O motor v2 leva minutos (PRETO 150: ~110 s), então a geração sai do request:
o router enfileira um job e devolve 202 {job_id}; a tela consulta o estado.

Regras
------
  * Fila simples em memória e UMA thread de trabalho: no máximo um job
    rodando no processo inteiro (o spyrrow já é um por vez — ver
    nesting_v2.encaixador._UM_POR_VEZ — e libera o GIL enquanto resolve, então
    a API continua respondendo).
  * Um job ativo (FILA/RODANDO) por chave — a chave é a OC ("oc", id) ou o
    pedido do Encaixe Rápido ("pedido", id). Pedir outro com um ativo é 409.
  * Cancelamento: flag checada no callback de progresso do motor, ou seja
    entre uma chamada do spyrrow e a próxima (entre mesas e fases). Quem
    cancela é a exceção GeracaoCancelada, que desfaz a transação — os
    encaixes anteriores ficam como estavam.
  * O resultado é gravado pela própria função do job, numa transação só, ao
    concluir; erro ou cancelamento não gravam nada.
  * Tudo em memória: reiniciar o backend perde a fila e o job em andamento,
    e a OC continua com os encaixes anteriores (nada foi gravado).

Estado de um job (Job.estado): job_id, oc_id, pedido_id, tipo, status (FILA,
RODANDO, CONCLUIDO, ERRO, CANCELADO), fase, mesa_atual, total_mesas,
aproveitamento_parcial, iniciado_em, concluido_em, erro, resultado.
"""

from __future__ import annotations

import logging
import queue
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from services.nesting_service import GeracaoCancelada

logger = logging.getLogger(__name__)

STATUS_ATIVOS = ("FILA", "RODANDO")

Chave = tuple[str, uuid.UUID]
# fn(db, job) → resultado (dict) — roda na thread de trabalho com sessão própria
Tarefa = Callable[[Session, "Job"], dict]


class ErroJob(Exception):
    """Regra dos jobs violada (router → HTTP `status`)."""

    def __init__(self, mensagem: str, status: int = 409):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status


def _agora() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Job:
    chave: Chave
    tarefa: Tarefa
    sessao: Callable[[], Session]
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "FILA"
    fase: str = "Na fila"
    mesa_atual: int = 0
    total_mesas: int = 0
    aproveitamento_parcial: float | None = None
    criado_em: datetime = field(default_factory=_agora)
    iniciado_em: datetime | None = None
    concluido_em: datetime | None = None
    erro: str | None = None
    resultado: dict | None = None
    _cancelar: threading.Event = field(default_factory=threading.Event, repr=False)

    # ── usado pela tarefa ────────────────────────────────────────────────

    @property
    def cancelado(self) -> bool:
        return self._cancelar.is_set()

    def checar(self) -> None:
        """Ponto de cancelamento: levanta GeracaoCancelada se pedido."""
        if self._cancelar.is_set():
            raise GeracaoCancelada("Geração cancelada pelo usuário.")

    def progresso(
        self,
        fase: str | None = None,
        mesa_atual: int | None = None,
        total_mesas: int | None = None,
        aproveitamento_parcial: float | None = None,
    ) -> None:
        """Callback de progresso do nesting_service — também é o ponto de
        cancelamento entre mesas/fases."""
        self.checar()
        if fase is not None:
            self.fase = fase
        if mesa_atual is not None:
            self.mesa_atual = mesa_atual
        if total_mesas is not None:
            self.total_mesas = total_mesas
        if aproveitamento_parcial is not None:
            self.aproveitamento_parcial = aproveitamento_parcial

    # ── saída ────────────────────────────────────────────────────────────

    @property
    def estado(self) -> dict:
        tipo, ident = self.chave
        return {
            "job_id": self.job_id,
            "tipo": tipo,
            "oc_id": str(ident) if tipo == "oc" else None,
            "pedido_id": str(ident) if tipo == "pedido" else None,
            "status": self.status,
            "fase": self.fase,
            "mesa_atual": self.mesa_atual,
            "total_mesas": self.total_mesas,
            "aproveitamento_parcial": self.aproveitamento_parcial,
            "cancelamento_pedido": self.cancelado and self.status in STATUS_ATIVOS,
            "criado_em": self.criado_em.isoformat(),
            "iniciado_em": self.iniciado_em.isoformat() if self.iniciado_em else None,
            "concluido_em": self.concluido_em.isoformat() if self.concluido_em else None,
            "erro": self.erro,
            "resultado": self.resultado,
        }


# ── Registro e fila ──────────────────────────────────────────────────────────

_trava = threading.Lock()
# Último job de cada chave (ativo ou terminado) — é o que GET .../job mostra.
_ultimo: dict[Chave, Job] = {}
_fila: queue.Queue[Job] = queue.Queue()
_trabalhador: threading.Thread | None = None


def enfileirar(chave: Chave, tarefa: Tarefa, sessao: Callable[[], Session]) -> Job:
    """Cria o job e põe na fila. `sessao` abre a sessão do banco que a
    tarefa usa na thread de trabalho (a do request fecha antes de o job
    rodar). ErroJob 409 se a chave já tem um job ativo."""
    global _trabalhador
    with _trava:
        atual = _ultimo.get(chave)
        if atual is not None and atual.status in STATUS_ATIVOS:
            raise ErroJob("Já existe uma geração de encaixes em andamento; aguarde ou cancele.", 409)
        job = Job(chave=chave, tarefa=tarefa, sessao=sessao)
        _ultimo[chave] = job
        if _trabalhador is None or not _trabalhador.is_alive():
            _trabalhador = threading.Thread(target=_trabalhar, name="nesting-jobs", daemon=True)
            _trabalhador.start()
    _fila.put(job)
    return job


def obter(chave: Chave) -> Job | None:
    return _ultimo.get(chave)


def ativo(chave: Chave) -> bool:
    job = _ultimo.get(chave)
    return job is not None and job.status in STATUS_ATIVOS


def cancelar(chave: Chave) -> Job:
    """Na fila: cancela na hora. Rodando: pede o cancelamento — o job para no
    próximo ponto de checagem (entre mesas/fases) e desfaz a transação."""
    with _trava:
        job = _ultimo.get(chave)
        if job is None or job.status not in STATUS_ATIVOS:
            raise ErroJob("Nenhuma geração de encaixes em andamento.", 404)
        job._cancelar.set()
        if job.status == "FILA":
            _terminar(job, "CANCELADO", fase="Cancelado")
    return job


def _terminar(job: Job, status: str, *, fase: str, erro: str | None = None) -> None:
    job.status = status
    job.fase = fase
    job.erro = erro
    job.concluido_em = _agora()


def _trabalhar() -> None:
    while True:
        job = _fila.get()
        try:
            _executar(job)
        finally:
            _fila.task_done()


def _executar(job: Job) -> None:
    with _trava:
        if job.status != "FILA":  # cancelado enquanto esperava
            return
        job.status = "RODANDO"
        job.fase = "Iniciando"
        job.iniciado_em = _agora()
    db = job.sessao()
    try:
        resultado = job.tarefa(db, job)
    except GeracaoCancelada:
        db.rollback()
        logger.info("[JOB] %s %s cancelado", job.chave[0], job.chave[1])
        _terminar(job, "CANCELADO", fase="Cancelado — encaixes anteriores mantidos")
    except Exception as exc:
        db.rollback()
        logger.exception("[JOB] %s %s falhou", job.chave[0], job.chave[1])
        _terminar(job, "ERRO", fase="Erro", erro=getattr(exc, "mensagem", None) or str(exc) or type(exc).__name__)
    else:
        job.resultado = resultado
        _terminar(job, "CONCLUIDO", fase="Concluído")
    finally:
        db.close()


def aguardar(chave: Chave, timeout: float | None = None) -> Job | None:
    """Espera o job da chave terminar (testes e scripts)."""
    import time

    fim = None if timeout is None else time.monotonic() + timeout
    while True:
        job = _ultimo.get(chave)
        if job is None or job.status not in STATUS_ATIVOS:
            return job
        if fim is not None and time.monotonic() > fim:
            return job
        time.sleep(0.05)
