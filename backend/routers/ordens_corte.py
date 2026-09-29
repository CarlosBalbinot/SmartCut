import uuid
from decimal import Decimal
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from database import get_db
from middleware.permissions import require_permission
from models.encaixe import Encaixe
from models.ordem_corte import (
    COMPRIMENTO_MAX_MAX_CM,
    COMPRIMENTO_MAX_MIN_CM,
    COMPRIMENTO_MAX_PADRAO_CM,
    QUALIDADE_PADRAO,
)
from models.pedido import PedidoVenda
from services import nesting_jobs, nesting_service
from services import ordem_corte_service as svc
from services.precificacao_service import get_ou_criar_config

router = APIRouter(prefix="/api/v1/ordens-corte", tags=["ordens-corte"])

# OC é produção de corte — usa as permissões do módulo de encaixes.
_MOD = "encaixes"
_VER = Depends(require_permission(_MOD, "ver"))
_CRIAR = Depends(require_permission(_MOD, "criar"))
_EDITAR = Depends(require_permission(_MOD, "editar"))
# Encaixe Rápido tem módulo próprio (mesmo de POST /encaixes/gerar).
_RAPIDO_VER = Depends(require_permission("encaixe_rapido", "ver"))
_RAPIDO_CRIAR = Depends(require_permission("encaixe_rapido", "criar"))
# Configurações > Produção — mesmos módulos do resto das Configurações.
_CONFIG_VER = Depends(require_permission("configuracoes_ver", "ver"))
_CONFIG_EDITAR = Depends(require_permission("configuracoes_editar", "ver"))

_Qualidade = Literal["RAPIDO", "EQUILIBRADO", "MAXIMO"]


class _TecidoEscolha(BaseModel):
    produto_pai_id: uuid.UUID
    cor: Optional[str] = None
    lote_id: Optional[uuid.UUID] = None


class _OrdemCorteUpdate(BaseModel):
    modo_camadas: Optional[Literal["SEM_SOBRA", "MENOS_ENFESTOS"]] = None
    # Limite de cada encaixe (mesa de corte), só em RASCUNHO — mudar exige regerar.
    comprimento_max_cm: Optional[int] = Field(None, ge=COMPRIMENTO_MAX_MIN_CM, le=COMPRIMENTO_MAX_MAX_CM)
    # Tempo do motor v2 na próxima geração (RASCUNHO).
    qualidade: Optional[_Qualidade] = None
    observacoes: Optional[str] = Field(None, max_length=2000)


class _ConfigProducao(BaseModel):
    motor_encaixe: Optional[Literal["v1", "v2"]] = None
    # Maior mesa de corte da fábrica — base do alerta de mesa maior.
    comprimento_max_mesa_cm: Optional[int] = Field(None, ge=COMPRIMENTO_MAX_MIN_CM, le=COMPRIMENTO_MAX_MAX_CM)
    alerta_economia_pct: Optional[Decimal] = Field(None, ge=0, le=100)


class _IniciarCorte(BaseModel):
    cortador: Optional[str] = Field(None, max_length=150)


class _ConsumoLote(BaseModel):
    lote_id: uuid.UUID
    # Opcional: sem kg_real, consome o peso planejado da OC para o lote.
    kg_real: Optional[float] = Field(None, ge=0)
    sobra_kg: Optional[float] = Field(None, ge=0)


class _ConcluirCorte(BaseModel):
    cortador: str = Field(..., min_length=1, max_length=150)
    consumos: List[_ConsumoLote] = Field(default_factory=list)
    observacao: Optional[str] = Field(None, max_length=2000)


class _ReabrirCorte(BaseModel):
    quem: str = Field(..., min_length=1, max_length=150)
    observacao: Optional[str] = Field(None, max_length=2000)


def _executar(fn, *args):
    try:
        return {"data": fn(*args), "error": None}
    except svc.ErroOC as exc:
        raise HTTPException(status_code=exc.status, detail=exc.mensagem)


# ── Totais ────────────────────────────────────────────────────────────────────


def _totais(db: Session, ocs: list[dict]) -> list[dict]:
    """Acrescenta os totais de cada OC (uma consulta para todas).

    Encaixe.comp_metros/peso_kg/custo_total são de UMA camada — os totais
    multiplicam por num_camadas. Um enfesto dividido em dois encaixes
    (parte 1/2 e 2/2) conta uma vez em enfestos e sobra_total.
    """
    ids = [uuid.UUID(oc["id"]) for oc in ocs]
    encaixes = (
        db.execute(select(Encaixe).where(Encaixe.ordem_corte_id.in_(ids), Encaixe.status != "deletado")).scalars().all()
        if ids
        else []
    )
    acc: dict[str, dict] = {
        str(i): {"enfestos": set(), "metros": 0.0, "peso": 0.0, "custo": 0.0, "sobra": 0, "lotes": {}} for i in ids
    }
    for e in encaixes:
        a = acc[str(e.ordem_corte_id)]
        mapa = e.mapa_json or {}
        camadas = e.num_camadas or 1
        peso = float(e.peso_kg or 0) * camadas
        a["metros"] += float(e.comp_metros or 0) * camadas
        a["peso"] += peso
        a["custo"] += float(e.custo_total or 0) * camadas
        enfesto = (str(e.lote_id), mapa.get("enfesto") or str(e.id))
        if enfesto not in a["enfestos"]:
            a["enfestos"].add(enfesto)
            a["sobra"] += mapa.get("sobra_total") or 0
        if e.lote_id:
            lote = str(e.lote_id)
            a["lotes"][lote] = a["lotes"].get(lote, 0.0) + peso

    for oc in ocs:
        a = acc[oc["id"]]
        oc.update(
            {
                "pecas_total": oc["total_pecas"],
                "enfestos": len(a["enfestos"]),
                "metros_total": round(a["metros"], 3),
                "peso_total_kg": round(a["peso"], 3),
                "custo_total": round(a["custo"], 2),
                "sobra_total": a["sobra"],
                # kg planejados por lote (seção Tecidos: planejado × disponível)
                "planejado_por_lote": {k: round(v, 3) for k, v in a["lotes"].items()},
            }
        )
    return ocs


def _executar_oc(db: Session, fn, *args):
    """_executar para operações que devolvem a OC completa — com totais."""
    resposta = _executar(fn, db, *args)
    _totais(db, [resposta["data"]])
    return resposta


# ── Jobs de geração (nesting_jobs) ────────────────────────────────────────────


def _sessao_do_job(db: Session):
    """Fábrica de sessão para a thread do job — mesmo banco do request (a
    sessão do request fecha antes de o job rodar) e mesma config do
    SessionLocal."""
    return sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False)


def _job(fn, *args):
    try:
        return fn(*args)
    except nesting_jobs.ErroJob as exc:
        raise HTTPException(status_code=exc.status, detail=exc.mensagem)


def _sem_job(oc_id: uuid.UUID) -> None:
    """A geração lê a OC no começo e grava minutos depois — mudar a OC no meio
    gravaria encaixes de uma OC que já não existe mais."""
    if nesting_jobs.ativo(("oc", oc_id)):
        raise HTTPException(
            status_code=409, detail="Há uma geração de encaixes em andamento nesta OC; aguarde ou cancele."
        )


def _enfileirar_oc(db: Session, oc_id: uuid.UUID) -> dict:
    job = _job(
        nesting_jobs.enfileirar,
        ("oc", oc_id),
        lambda sessao, j: svc.gerar_encaixes(sessao, oc_id, progresso=j.progresso),
        _sessao_do_job(db),
    )
    return {"job_id": job.job_id, "status": job.status}


def _estado_job(chave) -> dict:
    job = nesting_jobs.obter(chave)
    if job is None:
        raise HTTPException(status_code=404, detail="Nenhuma geração de encaixes nesta sessão do servidor.")
    return {"data": job.estado, "error": None}


# ── Configurações > Produção ──────────────────────────────────────────────────
# Rotas fixas antes de /{oc_id}.


@router.get("/configuracao-producao", response_model=dict, dependencies=[_CONFIG_VER])
def obter_config_producao(db: Session = Depends(get_db)):
    return {"data": nesting_service.config_producao(db), "error": None}


@router.patch("/configuracao-producao", response_model=dict, dependencies=[_CONFIG_EDITAR])
def atualizar_config_producao(payload: _ConfigProducao, db: Session = Depends(get_db)):
    cfg = get_ou_criar_config(db)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        if valor is not None:
            setattr(cfg, campo, valor)
    db.commit()
    return {"data": nesting_service.config_producao(db), "error": None}


# ── Encaixe Rápido em segundo plano ───────────────────────────────────────────


@router.post(
    "/encaixe-rapido/{pedido_id}",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[_RAPIDO_CRIAR],
)
def encaixe_rapido(
    pedido_id: uuid.UUID,
    comprimento_max_cm: int = Query(COMPRIMENTO_MAX_PADRAO_CM, ge=COMPRIMENTO_MAX_MIN_CM, le=COMPRIMENTO_MAX_MAX_CM),
    qualidade: _Qualidade = QUALIDADE_PADRAO,
    db: Session = Depends(get_db),
):
    """Encaixe Rápido (nesting_service.gerar_encaixe) como job: 202 {job_id};
    acompanhar em GET /encaixe-rapido/{pedido_id}/job."""
    if not db.get(PedidoVenda, pedido_id):
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")

    def _tarefa(sessao: Session, job) -> dict:
        try:
            return nesting_service.gerar_encaixe(
                sessao, pedido_id, comprimento_max_cm, qualidade=qualidade, progresso=job.progresso
            )
        except ValueError as exc:
            raise nesting_jobs.ErroJob(str(exc), 400)

    job = _job(nesting_jobs.enfileirar, ("pedido", pedido_id), _tarefa, _sessao_do_job(db))
    return {"data": {"job_id": job.job_id, "status": job.status}, "error": None}


@router.get("/encaixe-rapido/{pedido_id}/job", response_model=dict, dependencies=[_RAPIDO_VER])
def encaixe_rapido_job(pedido_id: uuid.UUID):
    return _estado_job(("pedido", pedido_id))


@router.post("/encaixe-rapido/{pedido_id}/job/cancelar", response_model=dict, dependencies=[_RAPIDO_CRIAR])
def encaixe_rapido_cancelar(pedido_id: uuid.UUID):
    return {"data": _job(nesting_jobs.cancelar, ("pedido", pedido_id)).estado, "error": None}


@router.post("/pedido/{pedido_id}", status_code=status.HTTP_201_CREATED, dependencies=[_CRIAR])
def criar(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    return _executar_oc(db, svc.criar_ordem_corte, pedido_id)


@router.get("/", response_model=dict, dependencies=[_VER])
def listar(
    status_oc: Optional[str] = Query(None, alias="status"),
    pedido_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
):
    # ?status=RASCUNHO — o parâmetro Python não se chama `status` para não
    # sombrear o fastapi.status usado nos status_code.
    return {"data": _totais(db, svc.listar(db, status=status_oc, pedido_id=pedido_id)), "error": None}


# Rota fixa antes de /{oc_id} (senão "lotes-disponiveis" cai na validação de UUID).
# ?oc_id= exclui a própria OC da reserva — a tela de escolha de lote de uma OC
# já enviada precisa do que sobraria para ela, não do que ela mesma travou.
@router.get("/lotes-disponiveis", response_model=dict, dependencies=[_VER])
def lotes_disponiveis(oc_id: Optional[uuid.UUID] = None, db: Session = Depends(get_db)):
    return {"data": svc.lotes_disponiveis(db, excluir_oc_id=oc_id), "error": None}


@router.get("/pedido/{pedido_id}", response_model=dict, dependencies=[_VER])
def obter_do_pedido(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    oc = svc.obter_do_pedido(db, pedido_id)
    if not oc:
        raise HTTPException(status_code=404, detail="Pedido sem Ordem de Corte ativa")
    return {"data": _totais(db, [oc])[0], "error": None}


@router.get("/{oc_id}", response_model=dict, dependencies=[_VER])
def obter(oc_id: uuid.UUID, db: Session = Depends(get_db)):
    oc = svc.obter(db, oc_id)
    if not oc:
        raise HTTPException(status_code=404, detail="Ordem de Corte não encontrada")
    return {"data": _totais(db, [oc])[0], "error": None}


@router.put("/{oc_id}/tecidos", response_model=dict, dependencies=[_EDITAR])
def definir_tecidos(oc_id: uuid.UUID, payload: list[_TecidoEscolha], db: Session = Depends(get_db)):
    _sem_job(oc_id)
    return _executar_oc(db, svc.definir_tecidos, oc_id, [p.model_dump() for p in payload])


@router.put("/{oc_id}", response_model=dict, dependencies=[_EDITAR])
def atualizar(oc_id: uuid.UUID, payload: _OrdemCorteUpdate, db: Session = Depends(get_db)):
    _sem_job(oc_id)
    return _executar_oc(db, svc.atualizar, oc_id, payload.model_dump(exclude_unset=True))


@router.post("/{oc_id}/atualizar-do-pedido", response_model=dict, dependencies=[_EDITAR])
def atualizar_do_pedido(oc_id: uuid.UUID, db: Session = Depends(get_db)):
    _sem_job(oc_id)
    return _executar_oc(db, svc.atualizar_do_pedido, oc_id)


@router.post("/{oc_id}/cancelar", response_model=dict, dependencies=[_EDITAR])
def cancelar(oc_id: uuid.UUID, db: Session = Depends(get_db)):
    _sem_job(oc_id)
    return _executar_oc(db, svc.cancelar, oc_id)


@router.post("/{oc_id}/enviar", response_model=dict, dependencies=[_EDITAR])
def enviar(oc_id: uuid.UUID, db: Session = Depends(get_db)):
    _sem_job(oc_id)
    return _executar_oc(db, svc.enviar_a_producao, oc_id)


# ── Produção (OC6a) ───────────────────────────────────────────────────────────


@router.post("/{oc_id}/voltar-rascunho", response_model=dict, dependencies=[_EDITAR])
def voltar_rascunho(oc_id: uuid.UUID, db: Session = Depends(get_db)):
    """ENVIADA → RASCUNHO: libera a reserva do lote (só se não começou a cortar)."""
    return _executar_oc(db, svc.voltar_rascunho, oc_id)


@router.post("/{oc_id}/iniciar", response_model=dict, dependencies=[_EDITAR])
def iniciar(oc_id: uuid.UUID, payload: _IniciarCorte, db: Session = Depends(get_db)):
    """ENVIADA → EM_CORTE: o corte começa (a reserva continua)."""
    return _executar_oc(db, svc.iniciar_corte, oc_id, payload.cortador)


@router.post("/{oc_id}/concluir", response_model=dict, dependencies=[_EDITAR])
def concluir(oc_id: uuid.UUID, payload: _ConcluirCorte, db: Session = Depends(get_db)):
    """EM_CORTE → CONCLUIDA: baixa o peso real de cada lote numa transação só."""
    return _executar_oc(
        db,
        svc.concluir,
        oc_id,
        payload.cortador,
        [c.model_dump() for c in payload.consumos],
        payload.observacao,
    )


@router.post("/{oc_id}/reabrir", response_model=dict, dependencies=[_EDITAR])
def reabrir(oc_id: uuid.UUID, payload: _ReabrirCorte, db: Session = Depends(get_db)):
    """CONCLUIDA → EM_CORTE: estorna o consumo e devolve o peso ao lote."""
    return _executar_oc(db, svc.reabrir, oc_id, payload.quem, payload.observacao)


@router.post(
    "/{oc_id}/gerar-encaixes", response_model=dict, status_code=status.HTTP_202_ACCEPTED, dependencies=[_CRIAR]
)
def gerar_encaixes(oc_id: uuid.UUID, db: Session = Depends(get_db)):
    """Gera (ou regera, substituindo os anteriores) os encaixes da OC em
    segundo plano: 202 {job_id}. Pendências e OC fora de RASCUNHO falham na
    hora; o resto (e o resultado) sai em GET /{oc_id}/job."""
    _executar(svc.validar_geracao, db, oc_id)
    return {"data": _enfileirar_oc(db, oc_id), "error": None}


@router.get("/{oc_id}/job", response_model=dict, dependencies=[_VER])
def estado_job(oc_id: uuid.UUID):
    """Estado da geração atual (ou da última) da OC — some ao reiniciar o backend."""
    return _estado_job(("oc", oc_id))


@router.post("/{oc_id}/job/cancelar", response_model=dict, dependencies=[_CRIAR])
def cancelar_job(oc_id: uuid.UUID):
    """Cancela a geração: os encaixes anteriores da OC ficam como estavam."""
    return {"data": _job(nesting_jobs.cancelar, ("oc", oc_id)).estado, "error": None}


@router.post(
    "/{oc_id}/aplicar-sugestao-mesa",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[_CRIAR],
)
def aplicar_sugestao_mesa(oc_id: uuid.UUID, db: Session = Depends(get_db)):
    """Troca o comprimento máximo pela mesa sugerida e dispara a nova geração."""
    _sem_job(oc_id)
    ordem = _executar_oc(db, svc.aplicar_sugestao_mesa, oc_id)["data"]
    _executar(svc.validar_geracao, db, oc_id)
    return {"data": {**_enfileirar_oc(db, oc_id), "ordem_corte": ordem}, "error": None}


@router.post("/{oc_id}/descartar-sugestao-mesa", response_model=dict, dependencies=[_EDITAR])
def descartar_sugestao_mesa(oc_id: uuid.UUID, db: Session = Depends(get_db)):
    """Esconde a sugestão de mesa maior até a próxima geração."""
    return _executar_oc(db, svc.descartar_sugestao_mesa, oc_id)


@router.get("/{oc_id}/simular", response_model=dict, dependencies=[_VER])
def simular(
    oc_id: uuid.UUID,
    modo: Optional[Literal["SEM_SOBRA", "MENOS_ENFESTOS"]] = None,
    db: Session = Depends(get_db),
):
    """Só o plano de enfesto (sem nesting) — padrão: o modo da OC."""
    return _executar(svc.simular, db, oc_id, modo)
