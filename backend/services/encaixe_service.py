import uuid

from sqlalchemy.orm import Session

from models.encaixe import Encaixe
from schemas.encaixe_schema import EncaixeOut


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


def deletar(db: Session, encaixe_id: uuid.UUID) -> bool:
    """Soft-delete: marca o encaixe como deletado. Retorna False se não encontrado."""
    encaixe = db.get(Encaixe, encaixe_id)
    if not encaixe or encaixe.status == "deletado":
        return False
    encaixe.status = "deletado"
    db.commit()
    return True
