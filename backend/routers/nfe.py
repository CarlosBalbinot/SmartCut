import os
import uuid
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from models.nfe import STATUS_VALIDOS, NotaFiscal
from models.pedido import PedidoVenda
from services.nfe_service import (
    assinar_xml, criar_pastas_nfe, gerar_danfe, montar_evento_cancelamento,
    montar_evento_cce, montar_xml_nfe, proximo_numero, transmitir_nfe,
)
from services.venda_service import get_ou_criar_empresa

router = APIRouter(prefix="/api/v1/nfe", tags=["nfe"])

_VER = require_permission("fiscal_nfe", "ver")
_CRIAR = require_permission("fiscal_nfe", "criar")
_TRANSMITIR = require_permission("fiscal_transmitir", "ver")
_CANCELAR = require_permission("fiscal_cancelar", "ver")
_CARTA_CORRECAO = require_permission("fiscal_carta_correcao", "ver")

_XML_GERADAS = "uploads/nfe/Geradas"
_XML_ENVIADAS = "uploads/nfe/Enviadas"
_XML_SOLIC_CANCELAMENTO = "uploads/nfe/SolicCancelamento"
_XML_CARTAS_CORRECAO = "uploads/nfe/CartasDeCorrecaoEnviadas"


# ── Schemas ─────────────────────────────────────────────────────────────

class NotaFiscalCreate(BaseModel):
    pedido_id: Optional[uuid.UUID] = None
    serie: str = Field(..., max_length=10)
    modelo: str = "55"
    data_emissao: date
    data_saida: Optional[date] = None
    hora_saida: Optional[str] = None


class NotaFiscalOut(BaseModel):
    id: int
    pedido_id: Optional[uuid.UUID] = None
    numero: int
    serie: str
    modelo: str
    ambiente: str
    chave_acesso: Optional[str] = None
    protocolo: Optional[str] = None
    status: str
    valor_nf: Optional[float] = None
    xml_path: Optional[str] = None
    danfe_path: Optional[str] = None
    data_emissao: datetime
    data_saida: Optional[datetime] = None
    hora_saida: Optional[str] = None
    data_autorizacao: Optional[datetime] = None
    motivo_rejeicao: Optional[str] = None
    carta_correcao: Optional[str] = None
    created_at: datetime
    destinatario: Optional[str] = None

    model_config = {"from_attributes": True}


def _montar_out(nfe: NotaFiscal, db: Session) -> NotaFiscalOut:
    out = NotaFiscalOut.model_validate(nfe)
    if nfe.pedido_id:
        pedido = db.get(PedidoVenda, nfe.pedido_id)
        out.destinatario = pedido.cliente_razao_social if pedido else None
    return out


class CartaCorrecaoIn(BaseModel):
    correcao: str = Field(..., min_length=15)


class CancelarIn(BaseModel):
    justificativa: str = Field(default="Cancelamento solicitado pelo emitente", min_length=15)


# ── Helpers ─────────────────────────────────────────────────────────────

def _get_nfe_ou_404(db: Session, nfe_id: int) -> NotaFiscal:
    nfe = db.get(NotaFiscal, nfe_id)
    if not nfe:
        raise HTTPException(status_code=404, detail="NF-e não encontrada")
    return nfe


# ── Rotas ───────────────────────────────────────────────────────────────

@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED, dependencies=[Depends(_CRIAR)])
def criar_nfe(payload: NotaFiscalCreate, db: Session = Depends(get_db)):
    criar_pastas_nfe()
    empresa = get_ou_criar_empresa(db)

    pedido = None
    if payload.pedido_id:
        pedido = db.get(PedidoVenda, payload.pedido_id)
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        if pedido.nfe_id is not None:
            raise HTTPException(status_code=400, detail="Este pedido já possui uma NF-e vinculada.")

    numero = proximo_numero(db, empresa, payload.serie)

    hora_saida = None
    data_saida_dt = None
    if payload.data_saida:
        hora = payload.hora_saida or "00:00:00"
        try:
            h, m, *_ = hora.split(":")
            hora_saida = f"{int(h):02d}:{int(m):02d}:00"
        except ValueError:
            hora_saida = "00:00:00"
        data_saida_dt = datetime.combine(payload.data_saida, time.min)

    nfe = NotaFiscal(
        pedido_id=payload.pedido_id,
        numero=numero,
        serie=payload.serie,
        modelo=payload.modelo,
        ambiente=empresa.ambiente_sefaz,
        status="Rascunho",
        data_emissao=datetime.combine(payload.data_emissao, datetime.now().time()),
        data_saida=data_saida_dt,
        hora_saida=hora_saida,
    )

    try:
        xml = montar_xml_nfe(pedido, nfe, empresa, db)
        xml_assinado = assinar_xml(xml, empresa)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    xml_path = os.path.join(_XML_GERADAS, f"{nfe.chave_acesso}.xml")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml_assinado)
    nfe.xml_path = xml_path

    db.add(nfe)
    db.commit()
    db.refresh(nfe)

    if pedido:
        pedido.nfe_id = nfe.id
        pedido.status = "Fechado"
        db.commit()

    return {"data": _montar_out(nfe, db), "error": None}


@router.get("/", response_model=dict, dependencies=[Depends(_VER)])
def listar_nfe(
    status_filtro: Optional[str] = None, serie: Optional[str] = None,
    mes: Optional[str] = None, db: Session = Depends(get_db),
):
    q = select(NotaFiscal)
    if status_filtro:
        if status_filtro not in STATUS_VALIDOS:
            raise HTTPException(status_code=400, detail=f"Status inválido: {status_filtro}")
        q = q.where(NotaFiscal.status == status_filtro)
    if serie:
        q = q.where(NotaFiscal.serie == serie)
    if mes:
        try:
            ano, m = (int(x) for x in mes.split("-"))
            inicio = datetime(ano, m, 1)
            fim = datetime(ano + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
            q = q.where(NotaFiscal.data_emissao >= inicio, NotaFiscal.data_emissao < fim)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Parâmetro 'mes' inválido — use AAAA-MM.")
    q = q.order_by(NotaFiscal.data_emissao.desc(), NotaFiscal.numero.desc())
    rows = db.execute(q).scalars().all()
    return {"data": [_montar_out(r, db) for r in rows], "error": None}


@router.get("/{nfe_id}", response_model=dict, dependencies=[Depends(_VER)])
def obter_nfe(nfe_id: int, db: Session = Depends(get_db)):
    nfe = _get_nfe_ou_404(db, nfe_id)
    return {"data": _montar_out(nfe, db), "error": None}


@router.post("/{nfe_id}/transmitir", response_model=dict, dependencies=[Depends(_TRANSMITIR)])
def transmitir(nfe_id: int, db: Session = Depends(get_db)):
    nfe = _get_nfe_ou_404(db, nfe_id)
    if nfe.status not in ("Rascunho", "Rejeitada"):
        raise HTTPException(status_code=400, detail=f"NF-e no status '{nfe.status}' não pode ser transmitida.")
    if not nfe.xml_path or not os.path.exists(nfe.xml_path):
        raise HTTPException(status_code=400, detail="XML da NF-e não encontrado em disco.")

    empresa = get_ou_criar_empresa(db)
    with open(nfe.xml_path, "r", encoding="utf-8") as f:
        xml_assinado = f.read()

    try:
        resultado = transmitir_nfe(xml_assinado, empresa)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Falha ao transmitir para a SEFAZ: {e}") from e

    cstat = resultado.get("cStat")
    if cstat == "100":
        nfe.status = "Autorizada"
        nfe.protocolo = resultado.get("protocolo")
        nfe.data_autorizacao = datetime.now()
        os.makedirs(_XML_ENVIADAS, exist_ok=True)
        novo_path = os.path.join(_XML_ENVIADAS, os.path.basename(nfe.xml_path))
        os.replace(nfe.xml_path, novo_path)
        nfe.xml_path = novo_path
    elif cstat in ("103", "104", "105"):
        nfe.status = "Aguardando"
    else:
        nfe.status = "Rejeitada"
        nfe.motivo_rejeicao = resultado.get("xMotivo")

    db.commit()
    db.refresh(nfe)
    return {"data": {"nfe": _montar_out(nfe, db), "resultado": resultado}, "error": None}


@router.post("/{nfe_id}/cancelar", response_model=dict, dependencies=[Depends(_CANCELAR)])
def cancelar(nfe_id: int, payload: CancelarIn, db: Session = Depends(get_db)):
    nfe = _get_nfe_ou_404(db, nfe_id)
    if nfe.status != "Autorizada":
        raise HTTPException(status_code=400, detail="Só é possível cancelar uma NF-e Autorizada.")
    if not nfe.data_autorizacao or datetime.now() - nfe.data_autorizacao > timedelta(hours=24):
        raise HTTPException(status_code=400, detail="Prazo de 24h para cancelamento já expirou.")

    empresa = get_ou_criar_empresa(db)
    try:
        xml_evento = montar_evento_cancelamento(empresa, nfe, payload.justificativa)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    os.makedirs(_XML_SOLIC_CANCELAMENTO, exist_ok=True)
    caminho = os.path.join(_XML_SOLIC_CANCELAMENTO, f"canc_{nfe.chave_acesso}.xml")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(xml_evento)

    # Evento assinado e salvo localmente — envio ao webservice de eventos
    # da SEFAZ (RecepcaoEvento) não está implementado (ver nfe_service.py).
    nfe.status = "Cancelada"
    if nfe.pedido_id:
        pedido = db.get(PedidoVenda, nfe.pedido_id)
        if pedido and pedido.nfe_id == nfe.id:
            pedido.nfe_id = None
            pedido.status = "Aberto"
    db.commit()
    db.refresh(nfe)
    return {"data": _montar_out(nfe, db), "error": None}


@router.get("/{nfe_id}/danfe", dependencies=[Depends(_VER)])
def obter_danfe(nfe_id: int, db: Session = Depends(get_db)):
    nfe = _get_nfe_ou_404(db, nfe_id)

    if nfe.danfe_path and os.path.exists(nfe.danfe_path):
        return FileResponse(nfe.danfe_path, media_type="application/pdf", filename=os.path.basename(nfe.danfe_path))

    if not nfe.xml_path or not os.path.exists(nfe.xml_path):
        raise HTTPException(status_code=400, detail="XML da NF-e não encontrado — não é possível gerar o DANFE.")

    empresa = get_ou_criar_empresa(db)
    with open(nfe.xml_path, "r", encoding="utf-8") as f:
        xml_assinado = f.read()

    danfe_path = gerar_danfe(xml_assinado, nfe, empresa)
    nfe.danfe_path = danfe_path
    db.commit()

    return FileResponse(danfe_path, media_type="application/pdf", filename=os.path.basename(danfe_path))


@router.post("/{nfe_id}/carta-correcao", response_model=dict, dependencies=[Depends(_CARTA_CORRECAO)])
def carta_correcao(nfe_id: int, payload: CartaCorrecaoIn, db: Session = Depends(get_db)):
    nfe = _get_nfe_ou_404(db, nfe_id)
    if nfe.status != "Autorizada":
        raise HTTPException(status_code=400, detail="Só é possível enviar carta de correção para uma NF-e Autorizada.")

    empresa = get_ou_criar_empresa(db)
    try:
        xml_evento = montar_evento_cce(empresa, nfe, payload.correcao)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    os.makedirs(_XML_CARTAS_CORRECAO, exist_ok=True)
    caminho = os.path.join(_XML_CARTAS_CORRECAO, f"cce_{nfe.chave_acesso}_{datetime.now():%Y%m%d%H%M%S}.xml")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(xml_evento)

    nfe.carta_correcao = payload.correcao
    db.commit()
    db.refresh(nfe)
    return {"data": _montar_out(nfe, db), "error": None}
