import uuid

from sqlalchemy.orm import Session, selectinload

from models.tecido import CorTecido, LoteTecido, ModeloTecido
from schemas.tecido_schema import CorCreate, CorOut, CorUpdate, LoteOut


def listar_por_modelo(db: Session, modelo_id: uuid.UUID) -> list[CorOut]:
    cores = (
        db.query(CorTecido)
        .filter(CorTecido.modelo_id == modelo_id)
        .order_by(CorTecido.nome_cor)
        .all()
    )
    return [CorOut.model_validate(c) for c in cores]


def obter(db: Session, cor_id: uuid.UUID) -> CorOut | None:
    cor = db.get(CorTecido, cor_id)
    return CorOut.model_validate(cor) if cor else None


def criar(db: Session, modelo_id: uuid.UUID, payload: CorCreate) -> CorOut:
    cor = CorTecido(modelo_id=modelo_id, **payload.model_dump())
    db.add(cor)
    db.commit()
    db.refresh(cor)
    return CorOut.model_validate(cor)


def atualizar(db: Session, cor_id: uuid.UUID, payload: CorUpdate) -> CorOut | None:
    cor = db.get(CorTecido, cor_id)
    if not cor:
        return None
    for campo, valor in payload.model_dump(exclude_none=True).items():
        setattr(cor, campo, valor)
    db.commit()
    db.refresh(cor)
    return CorOut.model_validate(cor)


def deletar(db: Session, cor_id: uuid.UUID) -> bool:
    cor = db.get(CorTecido, cor_id)
    if not cor:
        return False
    db.delete(cor)
    db.commit()
    return True


def recomendar_lote(db: Session, cor_id: uuid.UUID) -> LoteOut | None:
    """Retorna o lote mais antigo com status 'aberto'; se não houver, retorna o mais antigo 'intacto'."""
    lote_aberto = (
        db.query(LoteTecido)
        .filter(LoteTecido.cor_id == cor_id, LoteTecido.status == "aberto")
        .order_by(LoteTecido.data_compra)
        .first()
    )
    if lote_aberto:
        return LoteOut.model_validate(lote_aberto)

    lote_intacto = (
        db.query(LoteTecido)
        .filter(LoteTecido.cor_id == cor_id, LoteTecido.status == "intacto")
        .order_by(LoteTecido.data_compra)
        .first()
    )
    return LoteOut.model_validate(lote_intacto) if lote_intacto else None
