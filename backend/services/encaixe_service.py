import uuid

from sqlalchemy.orm import Session

from models.encaixe import Defeito, Encaixe
from models.pedido import PedidoVenda as Pedido
from schemas.encaixe_schema import EncaixeCreate, EncaixeOut


def listar(db: Session, pedido_id: uuid.UUID | None = None) -> list[EncaixeOut]:
    q = db.query(Encaixe).filter(Encaixe.status != "deletado")
    if pedido_id:
        q = q.filter(Encaixe.pedido_id == pedido_id)
    return [EncaixeOut.model_validate(e) for e in q.order_by(Encaixe.criado_em.desc()).all()]


def obter(db: Session, encaixe_id: uuid.UUID) -> EncaixeOut | None:
    encaixe = db.get(Encaixe, encaixe_id)
    if not encaixe or encaixe.status == "deletado":
        return None
    return EncaixeOut.model_validate(encaixe)


def gerar(db: Session, payload: EncaixeCreate) -> EncaixeOut:
    pedido = db.get(Pedido, payload.pedido_id)
    if not pedido:
        raise ValueError("Pedido não encontrado")

    encaixe = Encaixe(
        pedido_id=payload.pedido_id,
        num_camadas=payload.num_camadas,
        data_corte=payload.data_corte,
    )
    db.add(encaixe)
    db.flush()

    for d in payload.defeitos:
        defeito = Defeito(encaixe_id=encaixe.id, **d.model_dump())
        db.add(defeito)

    db.commit()
    db.refresh(encaixe)
    return EncaixeOut.model_validate(encaixe)


def deletar(db: Session, encaixe_id: uuid.UUID) -> bool:
    """Soft-delete: marca o encaixe como deletado. Retorna False se não encontrado."""
    encaixe = db.get(Encaixe, encaixe_id)
    if not encaixe or encaixe.status == "deletado":
        return False
    encaixe.status = "deletado"
    db.commit()
    return True


def gerar_relatorio(db: Session, encaixe_id: uuid.UUID) -> dict | None:
    encaixe = db.get(Encaixe, encaixe_id)
    if not encaixe or encaixe.status == "deletado":
        return None
    from services.report_service import gerar_pdf

    return gerar_pdf(encaixe)
