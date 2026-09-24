import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from models.pedido import PedidoVenda
from schemas.encaixe_schema import EncaixeCreate, EncaixeOut
from services import encaixe_service, nesting_service, report_service

router = APIRouter(prefix="/api/v1/encaixes", tags=["encaixes"])

_MOD = "encaixes"


@router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def listar_encaixes(pedido_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    encaixes = encaixe_service.listar(db, pedido_id=pedido_id)
    return {"data": encaixes, "error": None}


# ── Rota fixa deve vir ANTES das rotas com parâmetro ─────────────────────────
# Geração automática — é a ação do módulo "Encaixe Rápido", distinta da
# gestão manual de encaixes abaixo.

@router.post(
    "/gerar/{pedido_id}",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("encaixe_rapido", "criar"))],
)
def gerar_encaixe_automatico(
    pedido_id: uuid.UUID, db: Session = Depends(get_db)
):
    """Gera encaixes automáticos para todos os tecidos do pedido."""
    try:
        resultado = nesting_service.gerar_encaixe(db, pedido_id)
        return {"data": resultado, "error": None}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )
    except Exception as exc:
        # Qualquer outra falha (ex.: dado inconsistente, atributo ausente) não
        # pode virar um 500 sem corpo — vira mensagem clara para o frontend.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar encaixe: {exc}",
        )


@router.get("/{encaixe_id}", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def obter_encaixe(encaixe_id: uuid.UUID, db: Session = Depends(get_db)):
    encaixe = encaixe_service.obter(db, encaixe_id)
    if not encaixe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encaixe não encontrado")
    return {"data": encaixe, "error": None}


@router.post(
    "/", response_model=dict, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
def gerar_encaixe(payload: EncaixeCreate, db: Session = Depends(get_db)):
    encaixe = encaixe_service.gerar(db, payload)
    return {"data": encaixe, "error": None}


@router.delete(
    "/{encaixe_id}", status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(_MOD, "excluir"))],
)
def deletar_encaixe(encaixe_id: uuid.UUID, db: Session = Depends(get_db)):
    """Soft-delete: marca o encaixe como deletado."""
    ok = encaixe_service.deletar(db, encaixe_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encaixe não encontrado")
    return {"data": {"id": str(encaixe_id)}, "error": None}


@router.get(
    "/{encaixe_id}/relatorio", response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "ver"))],
)
def gerar_relatorio(encaixe_id: uuid.UUID, db: Session = Depends(get_db)):
    resultado = encaixe_service.gerar_relatorio(db, encaixe_id)
    if not resultado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encaixe não encontrado")
    return {"data": resultado, "error": None}


@router.get("/{pedido_id}/pdf", dependencies=[Depends(require_permission(_MOD, "ver"))])
def pdf_encaixe(pedido_id: uuid.UUID, db: Session = Depends(get_db)):
    """Gera PDF de relatório de corte com mapa visual de todos os enfestos do pedido."""
    encaixes = encaixe_service.listar(db, pedido_id=pedido_id)
    if not encaixes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum encaixe encontrado para este pedido.",
        )
    pedido_row = db.get(PedidoVenda, pedido_id)
    if not pedido_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido não encontrado.",
        )
    # gerar_pdf_encaixe só usa esses 3 campos de cabeçalho — todo o resto
    # (peças, tecido, mapa) já vem do mapa_json dos encaixes carregados
    # acima. O router legado de pedidos (que acessava
    # PedidoVenda.pedido_tecidos/.pecas) foi removido na reestruturação —
    # por isso o PDF passa a ser montado a partir do mapa_json.
    pedido = {
        "num_pedido": pedido_row.numero,
        "cliente": pedido_row.cliente_razao_social,
        "data_pedido": pedido_row.data_emissao.isoformat() if pedido_row.data_emissao else None,
    }
    pdf_bytes = report_service.gerar_pdf_encaixe(
        pedido, [e.model_dump() for e in encaixes]
    )
    num = str(pedido.get("num_pedido", "encaixe")).replace("/", "-").replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="encaixe-{num}.pdf"'},
    )
