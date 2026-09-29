import uuid
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from models.encaixe import Encaixe
from models.ordem_corte import COMPRIMENTO_MAX_MAX_CM, COMPRIMENTO_MAX_MIN_CM
from services import ordem_corte_service as svc

router = APIRouter(prefix="/api/v1/ordens-corte", tags=["ordens-corte"])

# OC é produção de corte — usa as permissões do módulo de encaixes.
_MOD = "encaixes"
_VER = Depends(require_permission(_MOD, "ver"))
_CRIAR = Depends(require_permission(_MOD, "criar"))
_EDITAR = Depends(require_permission(_MOD, "editar"))


class _TecidoEscolha(BaseModel):
    produto_pai_id: uuid.UUID
    cor: Optional[str] = None
    lote_id: Optional[uuid.UUID] = None


class _OrdemCorteUpdate(BaseModel):
    modo_camadas: Optional[Literal["SEM_SOBRA", "MENOS_ENFESTOS"]] = None
    # Limite de cada encaixe (mesa de corte), só em RASCUNHO — mudar exige regerar.
    comprimento_max_cm: Optional[int] = Field(None, ge=COMPRIMENTO_MAX_MIN_CM, le=COMPRIMENTO_MAX_MAX_CM)
    observacoes: Optional[str] = Field(None, max_length=2000)


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
    return _executar_oc(db, svc.definir_tecidos, oc_id, [p.model_dump() for p in payload])


@router.put("/{oc_id}", response_model=dict, dependencies=[_EDITAR])
def atualizar(oc_id: uuid.UUID, payload: _OrdemCorteUpdate, db: Session = Depends(get_db)):
    return _executar_oc(db, svc.atualizar, oc_id, payload.model_dump(exclude_unset=True))


@router.post("/{oc_id}/atualizar-do-pedido", response_model=dict, dependencies=[_EDITAR])
def atualizar_do_pedido(oc_id: uuid.UUID, db: Session = Depends(get_db)):
    return _executar_oc(db, svc.atualizar_do_pedido, oc_id)


@router.post("/{oc_id}/cancelar", response_model=dict, dependencies=[_EDITAR])
def cancelar(oc_id: uuid.UUID, db: Session = Depends(get_db)):
    return _executar_oc(db, svc.cancelar, oc_id)


@router.post("/{oc_id}/enviar", response_model=dict, dependencies=[_EDITAR])
def enviar(oc_id: uuid.UUID, db: Session = Depends(get_db)):
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


@router.post("/{oc_id}/gerar-encaixes", response_model=dict, status_code=status.HTTP_201_CREATED, dependencies=[_CRIAR])
def gerar_encaixes(oc_id: uuid.UUID, db: Session = Depends(get_db)):
    """Gera (ou regera, substituindo os anteriores) os encaixes da OC."""
    return _executar(svc.gerar_encaixes, db, oc_id)


@router.get("/{oc_id}/simular", response_model=dict, dependencies=[_VER])
def simular(
    oc_id: uuid.UUID,
    modo: Optional[Literal["SEM_SOBRA", "MENOS_ENFESTOS"]] = None,
    db: Session = Depends(get_db),
):
    """Só o plano de enfesto (sem nesting) — padrão: o modo da OC."""
    return _executar(svc.simular, db, oc_id, modo)
