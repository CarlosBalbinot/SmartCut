import uuid
from decimal import Decimal
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from database import get_db
from middleware.permissions import require_permission
from models.encaixe import Encaixe
from models.grupo_molde import GrupoMolde
from models.ordem_corte import (
    COMPRIMENTO_MAX_MAX_CM,
    COMPRIMENTO_MAX_MIN_CM,
    COMPRIMENTO_MAX_PADRAO_CM,
    QUALIDADE_PADRAO,
)
from models.pedido import ItemPedido, PedidoVenda
from models.tecido import CorTecido, LoteTecido
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

_Qualidade = Literal["AUTOMATICO", "RAPIDO", "EQUILIBRADO", "MAXIMO"]
_OrganizarPor = Literal["PRODUTO", "COR"]
# Enfesto: AUTOMATICO = o sistema decide (nesting_v2/decisor.py); valor fixo
# = escolha manual do "Avançado".
_TipoEnfesto = Literal["AUTOMATICO", "MESMA_FACE", "FACE_A_FACE"]
_ModoCamadas = Literal["AUTOMATICO", "SEM_SOBRA", "MENOS_ENFESTOS"]


class _TecidoEscolha(BaseModel):
    produto_pai_id: uuid.UUID
    cor: Optional[str] = None
    lote_id: Optional[uuid.UUID] = None


class _OrdemCorteUpdate(BaseModel):
    # "Avançado" (RASCUNHO): escolha manual do enfesto — AUTOMATICO devolve a
    # decisão ao sistema. Vale para a próxima geração.
    enfesto_tipo: Optional[_TipoEnfesto] = None
    enfesto_modo: Optional[_ModoCamadas] = None
    # Limite de cada encaixe (mesa de corte), só em RASCUNHO — mudar exige regerar.
    comprimento_max_cm: Optional[int] = Field(None, ge=COMPRIMENTO_MAX_MIN_CM, le=COMPRIMENTO_MAX_MAX_CM)
    # Tempo do motor v2 na próxima geração (RASCUNHO).
    qualidade: Optional[_Qualidade] = None
    # PRODUTO (cada produto corta à parte) ou COR (tudo do mesmo lote junto),
    # na próxima geração (RASCUNHO).
    organizar_por: Optional[_OrganizarPor] = None
    observacoes: Optional[str] = Field(None, max_length=2000)


class _ConfigProducao(BaseModel):
    # Maior mesa de corte da fábrica — base do alerta de mesa maior.
    comprimento_max_mesa_cm: Optional[int] = Field(None, ge=COMPRIMENTO_MAX_MIN_CM, le=COMPRIMENTO_MAX_MAX_CM)
    alerta_economia_pct: Optional[Decimal] = Field(None, ge=0, le=100)
    # Orçamento de tempo da qualidade "Automático" (ver planejamento/custo.py).
    tempo_maximo_oc_s: Optional[int] = Field(None, ge=30, le=7200)
    # Plano de corte por produto: tecido a mais aceito para simplificar (%).
    tolerancia_tecido_pct: Optional[Decimal] = Field(None, ge=0, le=20)


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
        db.execute(
            select(Encaixe)
            .options(selectinload(Encaixe.camadas_cor))
            .where(Encaixe.ordem_corte_id.in_(ids), Encaixe.status != "deletado")
        )
        .scalars()
        .all()
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
        grupo = mapa.get("grupo_corte") or str(e.lote_id)
        enfesto = (grupo, mapa.get("risco"), mapa.get("enfesto") or str(e.id))
        if enfesto not in a["enfestos"]:
            a["enfestos"].add(enfesto)
            a["sobra"] += mapa.get("sobra_total") or 0
        # Multicor: cada lote pelas linhas dele (Encaixe.consumo_por_lote).
        for lote_id, kg in e.consumo_por_lote().items():
            lote = str(lote_id)
            a["lotes"][lote] = a["lotes"].get(lote, 0.0) + kg

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
    tipo_enfesto: _TipoEnfesto = "AUTOMATICO",
    modo_camadas: _ModoCamadas = "AUTOMATICO",
    db: Session = Depends(get_db),
):
    """Encaixe Rápido (nesting_service.gerar_encaixe) como job: 202 {job_id};
    acompanhar em GET /encaixe-rapido/{pedido_id}/job. O enfesto é decidido
    pelo sistema; tipo_enfesto/modo_camadas fixos = "Avançado".

    Antes de enfileirar, valida as peças (largura × tecido, polígono): com
    problema que bloqueia, devolve 400 com a lista em vez de 202 — o
    frontend mostra e não gera (rota GET .../validar para ver antes)."""
    pedido = _carregar_pedido_rapido(db, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")

    problemas, _avisos = _validar_rapido(pedido, comprimento_max_cm)
    if problemas:
        raise HTTPException(status_code=400, detail="Não foi possível gerar o encaixe: " + " | ".join(problemas))

    def _tarefa(sessao: Session, job) -> dict:
        try:
            return nesting_service.gerar_encaixe(
                sessao,
                pedido_id,
                comprimento_max_cm,
                qualidade=qualidade,
                tipo_enfesto=tipo_enfesto,
                modo_camadas=modo_camadas,
                progresso=job.progresso,
            )
        except ValueError as exc:
            raise nesting_jobs.ErroJob(str(exc), 400)

    job = _job(nesting_jobs.enfileirar, ("pedido", pedido_id), _tarefa, _sessao_do_job(db))
    return {"data": {"job_id": job.job_id, "status": job.status}, "error": None}


def _carregar_pedido_rapido(db: Session, pedido_id: uuid.UUID) -> PedidoVenda | None:
    """Pedido com o que a validação/leitura precisam: grupo (com moldes) e
    lote (com cor/modelo) de cada item."""
    return (
        db.query(PedidoVenda)
        .options(
            selectinload(PedidoVenda.itens).selectinload(ItemPedido.grupo).selectinload(GrupoMolde.moldes),
            selectinload(PedidoVenda.itens)
            .selectinload(ItemPedido.lote)
            .selectinload(LoteTecido.cor)
            .selectinload(CorTecido.modelo),
        )
        .filter(PedidoVenda.id == pedido_id)
        .first()
    )


def _validar_rapido(pedido: PedidoVenda, comprimento_max_cm: int) -> tuple[list[str], list[str]]:
    """(problemas_bloqueantes, avisos) das peças do pedido — mensagens já
    citando molde e tecido (nesting_service.validar_entradas)."""
    entradas, _avisos = nesting_service.montar_pares_legado(pedido)
    return nesting_service.validar_entradas(entradas, comprimento_max_cm)


@router.get("/encaixe-rapido/{pedido_id}/job", response_model=dict, dependencies=[_RAPIDO_VER])
def encaixe_rapido_job(pedido_id: uuid.UUID):
    return _estado_job(("pedido", pedido_id))


@router.post("/encaixe-rapido/{pedido_id}/job/cancelar", response_model=dict, dependencies=[_RAPIDO_CRIAR])
def encaixe_rapido_cancelar(pedido_id: uuid.UUID):
    return {"data": _job(nesting_jobs.cancelar, ("pedido", pedido_id)).estado, "error": None}


@router.get("/encaixe-rapido/{pedido_id}/validar", response_model=dict, dependencies=[_RAPIDO_VER])
def encaixe_rapido_validar(
    pedido_id: uuid.UUID,
    comprimento_max_cm: int = Query(COMPRIMENTO_MAX_PADRAO_CM, ge=COMPRIMENTO_MAX_MIN_CM, le=COMPRIMENTO_MAX_MAX_CM),
    db: Session = Depends(get_db),
):
    """Valida as peças do Encaixe Rápido antes de gerar — o frontend chama
    depois de criar o pedido e mostra {:problemas, :avisos} no passo 1; se
    houver problema que bloqueia, aborta antes do POST."""
    pedido = _carregar_pedido_rapido(db, pedido_id)
    if not pedido or pedido.tipo != "encaixe_rapido":
        raise HTTPException(status_code=404, detail="Encaixe Rápido não encontrado.")
    problemas, avisos = _validar_rapido(pedido, comprimento_max_cm)
    return {"data": {"problemas": problemas, "avisos": avisos}, "error": None}


# ── Encaixe Rápido: leitura do resultado já gravado (tela com ?id= na URL) ───
#
# O job da geração vive só em memória (reiniciar o backend o perde); o que
# fica são os Encaixes do pedido. Esta rota (somente leitura) reconstrói a
# configuração da tela (nome, tecidos, peças, comprimento, qualidade) a partir
# dos itens/lotes e o resultado a partir dos Encaixes — para o frontend
# reabrir /producao/encaixe-rapido?id=<pedido_id> sem regenerar nada.

_QTD_CAMPOS_RAPIDO = ("qtd_p", "qtd_m", "qtd_g", "qtd_gg", "qtd_g1", "qtd_g2", "qtd_g3")


def _config_encaixe_rapido(pedido: PedidoVenda, encaixes: list[Encaixe]) -> dict:
    mapa = encaixes[0].mapa_json or {}
    tecidos: list[dict] = []
    vistos: set[str] = set()
    pecas: list[dict] = []
    for i, item in enumerate(pedido.itens or []):
        lote = item.lote
        tid = str(lote.id) if lote else ""
        if lote and tid not in vistos:
            vistos.add(tid)
            cor = lote.cor
            modelo = cor.modelo if cor else None
            tecidos.append(
                {
                    "_id": tid,
                    "modelo_id": str(modelo.id) if modelo else "",
                    "modelo_nome": modelo.nome if modelo else (cor.nome_cor if cor else ""),
                    "cor_id": str(cor.id) if cor else "",
                    "cor_nome": cor.nome_cor if cor else "",
                    "cor_largura_cm": float(cor.largura_util_cm) if cor and cor.largura_util_cm is not None else 0,
                    "lote_id": tid,
                    "lote_codigo": lote.codigo_lote,
                    "lote_peso_kg": float(lote.peso_disponivel_kg) if lote.peso_disponivel_kg is not None else 0,
                }
            )
        tem_plus = bool(getattr(item, "qtd_g1", None) or getattr(item, "qtd_g2", None) or getattr(item, "qtd_g3", None))
        peca = {
            "_id": f"pc-{i + 1}",
            "grupo_id": str(item.grupo_id) if item.grupo_id else "",
            "grupo_nome": item.grupo.nome if item.grupo else (item.descricao or ""),
            "grupo_codigo": item.grupo.codigo if item.grupo else "",
            "tem_plus": tem_plus,
            "cor": item.cor or "",
            "tecido_id": tid,
        }
        for campo in _QTD_CAMPOS_RAPIDO:
            peca[campo] = getattr(item, campo, None) or 0
        pecas.append(peca)

    return {
        "nome": pedido.observacoes_internas or "",
        "tecidos": tecidos,
        "pecas": pecas,
        "comprimento_max_cm": int(mapa.get("comprimento_max_cm") or 0) or COMPRIMENTO_MAX_PADRAO_CM,
        "qualidade": mapa.get("qualidade") or QUALIDADE_PADRAO,
        "qualidade_perfil": mapa.get("qualidade_perfil") or None,
    }


@router.get("/encaixe-rapido/{pedido_id}", response_model=dict, dependencies=[_RAPIDO_VER])
def encaixe_rapido_obter(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    """Lê um Encaixe Rápido existente (somente leitura): configuração da tela
    (nome, tecidos, peças, comprimento, qualidade) e o resultado (mesas).
    404 se o pedido não for um encaixe rápido ou não tiver mesas gravadas."""
    pedido = (
        db.query(PedidoVenda)
        .options(
            selectinload(PedidoVenda.itens).selectinload(ItemPedido.grupo),
            selectinload(PedidoVenda.itens)
            .selectinload(ItemPedido.lote)
            .selectinload(LoteTecido.cor)
            .selectinload(CorTecido.modelo),
        )
        .filter(PedidoVenda.id == pedido_id)
        .first()
    )
    if not pedido or pedido.tipo != "encaixe_rapido":
        raise HTTPException(status_code=404, detail="Encaixe Rápido não encontrado.")
    encaixes = sorted(
        (e for e in pedido.encaixes if e.status != "deletado"),
        key=lambda e: (e.numero or 0, e.criado_em),
    )
    if not encaixes:
        raise HTTPException(status_code=404, detail="Encaixe Rápido sem mesas geradas.")

    resumos = [nesting_service._resumo(e) for e in encaixes]
    # Decisão do enfesto: gravada na primeira mesa de cada lote.
    decisoes = [
        {"lote_id": (e.mapa_json or {}).get("lote_id"), "tecido": (e.mapa_json or {}).get("tecido_nome"), **d}
        for e in encaixes
        if (d := (e.mapa_json or {}).get("decisao_enfesto"))
    ]
    return {
        "data": {
            "config": _config_encaixe_rapido(pedido, encaixes),
            "resultado": {
                "pedido_id": str(pedido_id),
                "encaixes": resumos,
                "comprimento_max_cm": resumos[0].get("comprimento_max_cm") or COMPRIMENTO_MAX_PADRAO_CM,
                "decisoes": decisoes,
                "avisos": [],
            },
        },
        "error": None,
    }


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
