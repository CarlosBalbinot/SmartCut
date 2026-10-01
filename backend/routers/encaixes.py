import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from middleware.permissions import require_permission
from models.encaixe import Encaixe
from models.ordem_corte import OrdemCorte
from models.pedido import PedidoVenda
from models.tecido import CorTecido, LoteTecido
from services import encaixe_service
from services.ordem_corte_service import numero_fmt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/encaixes", tags=["encaixes"])

_MOD = "encaixes"


# ── Contexto (OC / pedido) ────────────────────────────────────────────────────


def _contexto(db: Session, encaixes) -> dict[str, dict]:
    """OC e pedido de cada encaixe (duas consultas para a lista inteira).
    Encaixe antigo pode não ter nenhum dos dois."""
    oc_ids = {e.ordem_corte_id for e in encaixes if e.ordem_corte_id}
    ped_ids = {e.pedido_id for e in encaixes if e.pedido_id}
    ocs = {o.id: o for o in db.execute(select(OrdemCorte).where(OrdemCorte.id.in_(oc_ids))).scalars()} if oc_ids else {}
    peds = (
        {p.id: p for p in db.execute(select(PedidoVenda).where(PedidoVenda.id.in_(ped_ids))).scalars()}
        if ped_ids
        else {}
    )
    saida: dict[str, dict] = {}
    for e in encaixes:
        oc = ocs.get(e.ordem_corte_id)
        ped = peds.get(e.pedido_id)
        saida[str(e.id)] = {
            "ordem_corte": (
                {"id": str(oc.id), "numero": oc.numero, "numero_fmt": numero_fmt(oc.numero), "status": oc.status}
                if oc
                else None
            ),
            "pedido": (
                {"id": str(ped.id), "numero": ped.numero, "cliente": ped.cliente_razao_social, "tipo": ped.tipo}
                if ped
                else None
            ),
        }
    return saida


def _totais_camadas(row: Encaixe) -> dict:
    """Totais de TODAS as camadas do encaixe.

    Encaixe.peso_kg/custo_total/comp_metros são de UMA camada — os totais
    multiplicam por num_camadas. Mesma regra do detalhe (obter_encaixe), para
    o card da listagem bater com a tela do encaixe.
    """
    camadas = row.num_camadas or 1
    return {
        "comp_total_m": round(float(row.comp_metros or 0) * camadas, 3),
        "peso_total_kg": round(float(row.peso_kg or 0) * camadas, 3),
        "custo_total_camadas": round(float(row.custo_total or 0) * camadas, 2),
    }


@router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def listar_encaixes(pedido_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    """Lista com a OC e o pedido de cada encaixe (a tela agrupa por OC).

    ?pedido_id= é legado (tela de encaixe antiga, aberta pelo id do pedido):
    hoje só o redirecionamento de links antigos da EncaixePage usa.
    """
    if pedido_id:
        logger.info("[ENCAIXES] listagem legada por pedido_id=%s", pedido_id)
    encaixes = encaixe_service.listar(db, pedido_id=pedido_id)
    linhas = [db.get(Encaixe, e.id) for e in encaixes]
    ctx = _contexto(db, linhas)
    return {
        "data": [{**e.model_dump(), **ctx[str(row.id)], **_totais_camadas(row)} for e, row in zip(encaixes, linhas)],
        "error": None,
    }


@router.get("/{encaixe_id}", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def obter_encaixe(encaixe_id: uuid.UUID, db: Session = Depends(get_db)):
    """Encaixe completo pelo próprio id: OC e pedido (quando houver), lote,
    peças por tamanho, totais de todas as camadas e anterior/próximo.

    peso_kg/custo_total/comp_metros do Encaixe são de UMA camada; os
    *_total multiplicam por num_camadas. A navegação percorre os encaixes
    da mesma OC — sem OC, os do mesmo pedido (Encaixe Rápido com vários
    lotes) — em ordem de número.
    """
    encaixe = encaixe_service.obter(db, encaixe_id)
    if not encaixe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encaixe não encontrado")
    row = db.get(Encaixe, encaixe_id)
    mapa = row.mapa_json or {}
    camadas = row.num_camadas or 1

    lote = None
    if row.lote_id:
        lote = db.execute(
            select(LoteTecido)
            .where(LoteTecido.id == row.lote_id)
            .options(selectinload(LoteTecido.cor).selectinload(CorTecido.modelo))
        ).scalar_one_or_none()

    if row.ordem_corte_id:
        filtro = Encaixe.ordem_corte_id == row.ordem_corte_id
    elif row.pedido_id:
        filtro = (Encaixe.pedido_id == row.pedido_id) & Encaixe.ordem_corte_id.is_(None)
    else:
        filtro = Encaixe.id == row.id
    irmaos = (
        db.execute(
            select(Encaixe.id).where(filtro, Encaixe.status != "deletado").order_by(Encaixe.numero, Encaixe.criado_em)
        )
        .scalars()
        .all()
    )
    pos = irmaos.index(row.id) if row.id in irmaos else 0

    return {
        "data": {
            **encaixe.model_dump(),
            **_contexto(db, [row])[str(row.id)],
            "lote": (
                {
                    "id": str(lote.id),
                    "codigo_lote": lote.codigo_lote,
                    "modelo": lote.cor.modelo.nome if lote.cor and lote.cor.modelo else None,
                    "cor_tecido": lote.cor.nome_cor if lote.cor else None,
                }
                if lote
                else None
            ),
            "tecido_nome": mapa.get("tecido_nome"),
            "enfesto": mapa.get("enfesto"),
            "parte": mapa.get("parte"),
            "pecas_por_tamanho": mapa.get("pecas_por_tamanho"),
            "sobra_total": mapa.get("sobra_total"),
            "aproveitamento_pct": (
                round(100.0 - float(row.desperdicio_pct), 2) if row.desperdicio_pct is not None else None
            ),
            "comp_total_m": round(float(row.comp_metros or 0) * camadas, 3),
            "peso_total_kg": round(float(row.peso_kg or 0) * camadas, 3),
            "custo_total_camadas": round(float(row.custo_total or 0) * camadas, 2),
            "navegacao": {
                "posicao": pos + 1,
                "total": len(irmaos),
                "anterior_id": str(irmaos[pos - 1]) if pos > 0 else None,
                "proximo_id": str(irmaos[pos + 1]) if pos + 1 < len(irmaos) else None,
            },
        },
        "error": None,
    }


@router.delete(
    "/{encaixe_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(_MOD, "excluir"))],
)
def deletar_encaixe(encaixe_id: uuid.UUID, db: Session = Depends(get_db)):
    """Soft-delete: marca o encaixe como deletado."""
    ok = encaixe_service.deletar(db, encaixe_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encaixe não encontrado")
    return {"data": {"id": str(encaixe_id)}, "error": None}
