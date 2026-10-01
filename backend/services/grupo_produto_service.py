import uuid

from sqlalchemy.orm import Session

from models.produto import GrupoProduto
from schemas.produto_schema import GrupoProdutoCreate, GrupoProdutoUpdate
from services import sequencia_service

# Sequência do código do grupo (services/sequencia_service.py, F0 passo 1d).
SEQ_GRUPO = "grupo_produto"


def _ultimo_codigo(db: Session) -> int:
    """Maior código numérico já usado (códigos não numéricos são ignorados) —
    ponto de partida da sequência no primeiro uso."""
    max_val = 0
    for (codigo,) in db.query(GrupoProduto.codigo).all():
        try:
            max_val = max(max_val, int(codigo))
        except (ValueError, TypeError):
            pass
    return max_val


def _proximo_codigo(db: Session) -> str:
    return str(sequencia_service.proximo(db, SEQ_GRUPO, _ultimo_codigo)).zfill(3)


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
