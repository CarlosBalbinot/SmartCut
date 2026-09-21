import uuid

from sqlalchemy.orm import Session

from models.produto import ColunaGrade, LinhaGrade
from schemas.produto_schema import GradeItemCreate


def listar_linhas(db: Session, situacao: str | None = None) -> list[LinhaGrade]:
    q = db.query(LinhaGrade)
    if situacao:
        q = q.filter(LinhaGrade.situacao == situacao)
    return q.order_by(LinhaGrade.nome).all()


def criar_linha(db: Session, payload: GradeItemCreate) -> LinhaGrade:
    item = LinhaGrade(nome=payload.nome, situacao=payload.situacao)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def listar_colunas(db: Session, situacao: str | None = None) -> list[ColunaGrade]:
    q = db.query(ColunaGrade)
    if situacao:
        q = q.filter(ColunaGrade.situacao == situacao)
    return q.order_by(ColunaGrade.nome).all()


def criar_coluna(db: Session, payload: GradeItemCreate) -> ColunaGrade:
    item = ColunaGrade(nome=payload.nome, situacao=payload.situacao)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
