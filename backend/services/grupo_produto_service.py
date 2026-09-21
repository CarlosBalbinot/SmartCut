import uuid

from sqlalchemy.orm import Session

from models.produto import GrupoProduto
from schemas.produto_schema import GrupoProdutoCreate, GrupoProdutoUpdate


def _proximo_codigo(db: Session) -> str:
    codigos = [row[0] for row in db.query(GrupoProduto.codigo).all()]
    max_val = 0
    for codigo in codigos:
        try:
            n = int(codigo)
            if n > max_val:
                max_val = n
        except (ValueError, TypeError):
            pass
    return str(max_val + 1).zfill(3)


def listar(db: Session, situacao: str | None = None) -> list[GrupoProduto]:
    q = db.query(GrupoProduto)
    if situacao:
        q = q.filter(GrupoProduto.situacao == situacao)
    return q.order_by(GrupoProduto.codigo).all()


def obter(db: Session, grupo_id: uuid.UUID) -> GrupoProduto | None:
    return db.get(GrupoProduto, grupo_id)


def criar(db: Session, payload: GrupoProdutoCreate) -> GrupoProduto:
    grupo = GrupoProduto(
        codigo=_proximo_codigo(db),
        nome=payload.nome,
        prefixo=payload.prefixo.upper(),
        situacao=payload.situacao,
    )
    db.add(grupo)
    db.commit()
    db.refresh(grupo)
    return grupo


def atualizar(db: Session, grupo_id: uuid.UUID, payload: GrupoProdutoUpdate) -> GrupoProduto | None:
    grupo = db.get(GrupoProduto, grupo_id)
    if not grupo:
        return None
    dados = payload.model_dump(exclude_unset=True)
    if "prefixo" in dados and dados["prefixo"] is not None:
        dados["prefixo"] = dados["prefixo"].upper()
    for campo, valor in dados.items():
        setattr(grupo, campo, valor)
    db.commit()
    db.refresh(grupo)
    return grupo


def deletar(db: Session, grupo_id: uuid.UUID) -> bool:
    """Levanta ValueError se o grupo tiver produtos cadastrados."""
    grupo = db.get(GrupoProduto, grupo_id)
    if not grupo:
        return False
    if grupo.produtos:
        raise ValueError("Não é possível excluir um grupo com produtos cadastrados.")
    db.delete(grupo)
    db.commit()
    return True
