import uuid

from sqlalchemy.orm import Session, selectinload

from models.produto import GrupoProduto, Produto
from schemas.produto_schema import ProdutoCreate, ProdutoUpdate


def _opts():
    return [
        selectinload(Produto.grupo),
        selectinload(Produto.linha_grade),
        selectinload(Produto.coluna_grade),
    ]


def _proximo_codigo(db: Session, grupo: GrupoProduto) -> str:
    prefixo = f"{grupo.prefixo}-"
    codigos = [
        row[0] for row in
        db.query(Produto.codigo).filter(Produto.grupo_id == grupo.id).all()
    ]
    max_val = 0
    for codigo in codigos:
        if not codigo.startswith(prefixo):
            continue
        try:
            n = int(codigo[len(prefixo):])
            if n > max_val:
                max_val = n
        except ValueError:
            pass
    return f"{grupo.prefixo}-{max_val + 1:03d}"


def listar(db: Session, status: str | None = None, grupo_id: uuid.UUID | None = None) -> list[Produto]:
    q = db.query(Produto).options(*_opts())
    if status:
        q = q.filter(Produto.status == status)
    if grupo_id:
        q = q.filter(Produto.grupo_id == grupo_id)
    return q.order_by(Produto.codigo).all()


def obter(db: Session, produto_id: uuid.UUID) -> Produto | None:
    return (
        db.query(Produto)
        .options(*_opts())
        .filter(Produto.id == produto_id)
        .first()
    )


def criar(db: Session, payload: ProdutoCreate) -> Produto:
    grupo = db.get(GrupoProduto, payload.grupo_id)
    if not grupo:
        raise ValueError("Grupo de produto não encontrado.")

    dados = payload.model_dump()
    produto = Produto(codigo=_proximo_codigo(db, grupo), **dados)
    db.add(produto)
    db.commit()
    db.refresh(produto)
    return obter(db, produto.id)


def atualizar(db: Session, produto_id: uuid.UUID, payload: ProdutoUpdate) -> Produto | None:
    produto = db.get(Produto, produto_id)
    if not produto:
        return None

    dados = payload.model_dump(exclude_unset=True)
    novo_grupo_id = dados.get("grupo_id")
    if novo_grupo_id and novo_grupo_id != produto.grupo_id:
        grupo = db.get(GrupoProduto, novo_grupo_id)
        if not grupo:
            raise ValueError("Grupo de produto não encontrado.")
        produto.codigo = _proximo_codigo(db, grupo)

    for campo, valor in dados.items():
        setattr(produto, campo, valor)

    db.commit()
    db.refresh(produto)
    return obter(db, produto.id)


def deletar(db: Session, produto_id: uuid.UUID) -> bool:
    produto = db.get(Produto, produto_id)
    if not produto:
        return False
    db.delete(produto)
    db.commit()
    return True
