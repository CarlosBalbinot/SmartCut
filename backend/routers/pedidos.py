import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from schemas.pedido_schema import (
    AdicionarGrupoPecaCreate,
    PedidoCreate,
    PedidoStatusUpdate,
    PedidoTecidoCreate,
    PedidoUpdate,
)
from services import pedido_service
from services import report_service

router = APIRouter(prefix="/api/v1/pedidos", tags=["pedidos"])


# ── Rota fixa deve vir ANTES das rotas com parâmetro ─────────────────

@router.get("/proximo-numero", response_model=dict)
def proximo_numero(db: Session = Depends(get_db)):
    return {"data": {"numero": pedido_service.proximo_numero(db)}, "error": None}


@router.get("/", response_model=dict)
def listar_pedidos(db: Session = Depends(get_db)):
    return {"data": pedido_service.listar(db), "error": None}


@router.get("/{pedido_id}", response_model=dict)
def obter_pedido(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    pedido = pedido_service.obter_detalhe(db, pedido_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": pedido, "error": None}


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def criar_pedido(payload: PedidoCreate, db: Session = Depends(get_db)):
    try:
        pedido = pedido_service.criar(db, payload)
        return {"data": pedido, "error": None}
    except IntegrityError:
        db.rollback()
        sugestao = pedido_service.proximo_numero(db)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"O número de pedido já está em uso. Sugerimos o número: {sugestao}",
        )


@router.patch("/{pedido_id}", response_model=dict)
def atualizar_pedido(
    pedido_id: uuid.UUID, payload: PedidoUpdate, db: Session = Depends(get_db)
):
    pedido = pedido_service.atualizar(db, pedido_id, payload)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": pedido, "error": None}


@router.patch("/{pedido_id}/status", response_model=dict)
def alterar_status(
    pedido_id: uuid.UUID, payload: PedidoStatusUpdate, db: Session = Depends(get_db)
):
    pedido = pedido_service.alterar_status(db, pedido_id, payload)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": pedido, "error": None}


@router.delete("/{pedido_id}", response_model=dict)
def excluir_pedido(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    ok = pedido_service.excluir(db, pedido_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": {"excluido": True}, "error": None}


@router.post("/{pedido_id}/duplicar", response_model=dict, status_code=status.HTTP_201_CREATED)
def duplicar_pedido(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    novo = pedido_service.duplicar(db, pedido_id)
    if not novo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": novo, "error": None}


# ── Tecidos do pedido ─────────────────────────────────────────────────

@router.post("/{pedido_id}/tecidos", response_model=dict, status_code=status.HTTP_201_CREATED)
def adicionar_tecido(
    pedido_id: uuid.UUID, payload: PedidoTecidoCreate, db: Session = Depends(get_db)
):
    pedido = pedido_service.adicionar_tecido(db, pedido_id, payload)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": pedido, "error": None}


@router.delete("/{pedido_id}/tecidos/{pt_id}", response_model=dict)
def remover_tecido(
    pedido_id: uuid.UUID, pt_id: uuid.UUID, db: Session = Depends(get_db)
):
    pedido = pedido_service.remover_tecido(db, pedido_id, pt_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": pedido, "error": None}


# ── Peças ─────────────────────────────────────────────────────────────

@router.post("/{pedido_id}/pecas", response_model=dict, status_code=status.HTTP_201_CREATED)
def adicionar_grupo_pecas(
    pedido_id: uuid.UUID,
    payload: AdicionarGrupoPecaCreate,
    db: Session = Depends(get_db),
):
    pedido = pedido_service.adicionar_grupo_pecas(db, pedido_id, payload)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": pedido, "error": None}


@router.delete("/{pedido_id}/pecas/{grupo_id}/{tamanho}", response_model=dict)
def remover_grupo_pecas(
    pedido_id: uuid.UUID,
    grupo_id: uuid.UUID,
    tamanho: str,
    db: Session = Depends(get_db),
):
    pedido = pedido_service.remover_grupo_pecas(db, pedido_id, grupo_id, tamanho)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": pedido, "error": None}


# ── Resumo e relatório ────────────────────────────────────────────────

@router.get("/{pedido_id}/resumo-corte", response_model=dict)
def resumo_corte(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    resumo = pedido_service.calcular_resumo_corte(db, pedido_id)
    if not resumo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return {"data": resumo, "error": None}


@router.get("/{pedido_id}/relatorio-pdf")
def relatorio_pdf(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    pedido = pedido_service.obter_detalhe(db, pedido_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    resumo = pedido_service.calcular_resumo_corte(db, pedido_id)
    pdf_bytes = report_service.gerar_pdf_pedido(pedido, resumo)
    num = pedido["num_pedido"].replace("/", "-").replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="pedido-{num}.pdf"'},
    )
