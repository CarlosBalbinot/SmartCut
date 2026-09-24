from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from models.transportadora import Transportadora
from schemas.transportadora_schema import (
    TransportadoraCreate,
    TransportadoraResponse,
    TransportadoraUpdate,
)

router = APIRouter(prefix="/api/v1/transportadoras", tags=["transportadoras"])

_MOD = "cadastros_transportadoras"


def _proximo_codigo(db: Session) -> str:
    codigos = [row[0] for row in db.query(Transportadora.codigo).filter(Transportadora.codigo.isnot(None)).all()]
    max_val = 0
    for codigo in codigos:
        try:
            n = int(codigo)
            if n > max_val:
                max_val = n
        except (ValueError, TypeError):
            pass
    return str(max_val + 1).zfill(6)


@router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def listar_transportadoras(
    busca: str = "",
    bloqueado: bool | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Transportadora)
    if bloqueado is not None:
        q = q.filter(Transportadora.bloqueado == bloqueado)
    if busca:
        termo = f"%{busca}%"
        q = q.filter(Transportadora.nome.ilike(termo) | Transportadora.cpf_cnpj.ilike(termo))
    transportadoras = q.order_by(Transportadora.nome).all()
    return {"data": [TransportadoraResponse.model_validate(t) for t in transportadoras], "error": None}


@router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
def criar_transportadora(payload: TransportadoraCreate, db: Session = Depends(get_db)):
    transportadora = Transportadora(codigo=_proximo_codigo(db), **payload.model_dump())
    db.add(transportadora)
    db.commit()
    db.refresh(transportadora)
    return {"data": TransportadoraResponse.model_validate(transportadora), "error": None}


@router.get(
    "/{transportadora_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "ver"))],
)
def obter_transportadora(transportadora_id: int, db: Session = Depends(get_db)):
    transportadora = db.query(Transportadora).filter(Transportadora.id == transportadora_id).first()
    if not transportadora:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transportadora não encontrada")
    return {"data": TransportadoraResponse.model_validate(transportadora), "error": None}


@router.put(
    "/{transportadora_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "editar"))],
)
def atualizar_transportadora(transportadora_id: int, payload: TransportadoraUpdate, db: Session = Depends(get_db)):
    transportadora = db.query(Transportadora).filter(Transportadora.id == transportadora_id).first()
    if not transportadora:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transportadora não encontrada")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(transportadora, campo, valor)
    db.commit()
    db.refresh(transportadora)
    return {"data": TransportadoraResponse.model_validate(transportadora), "error": None}


@router.delete(
    "/{transportadora_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "excluir"))],
)
def excluir_transportadora(transportadora_id: int, db: Session = Depends(get_db)):
    transportadora = db.query(Transportadora).filter(Transportadora.id == transportadora_id).first()
    if not transportadora:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transportadora não encontrada")
    db.delete(transportadora)
    db.commit()
    return {"data": {"excluido": True}, "error": None}
