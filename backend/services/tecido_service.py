import uuid

from sqlalchemy.orm import Session

from models.tecido import Tecido
from schemas.tecido_schema import TecidoCreate, TecidoOut, TecidoUpdate


def listar(db: Session) -> list[TecidoOut]:
    tecidos = db.query(Tecido).order_by(Tecido.criado_em.desc()).all()
    return [TecidoOut.model_validate(t) for t in tecidos]


def obter(db: Session, tecido_id: uuid.UUID) -> TecidoOut | None:
    tecido = db.get(Tecido, tecido_id)
    return TecidoOut.model_validate(tecido) if tecido else None


def criar(db: Session, payload: TecidoCreate) -> TecidoOut:
    tecido = Tecido(**payload.model_dump())
    db.add(tecido)
    db.commit()
    db.refresh(tecido)
    return TecidoOut.model_validate(tecido)


def atualizar(
    db: Session, tecido_id: uuid.UUID, payload: TecidoUpdate
) -> TecidoOut | None:
    tecido = db.get(Tecido, tecido_id)
    if not tecido:
        return None
    for campo, valor in payload.model_dump(exclude_none=True).items():
        setattr(tecido, campo, valor)
    db.commit()
    db.refresh(tecido)
    return TecidoOut.model_validate(tecido)


def deletar(db: Session, tecido_id: uuid.UUID) -> bool:
    tecido = db.get(Tecido, tecido_id)
    if not tecido:
        return False
    db.delete(tecido)
    db.commit()
    return True
