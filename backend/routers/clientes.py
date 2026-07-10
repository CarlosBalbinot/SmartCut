from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.cliente import Cliente
from schemas.cliente_schema import ClienteCreate, ClienteResponse, ClienteUpdate

router = APIRouter(prefix="/api/v1/clientes", tags=["clientes"])


@router.get("/cnpj/{cnpj}", response_model=dict)
def buscar_por_cnpj(cnpj: str, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.cnpj == cnpj, Cliente.ativo == True).first()
    if not cliente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    return {"data": ClienteResponse.model_validate(cliente), "error": None}


@router.get("/", response_model=dict)
def listar_clientes(busca: str = "", db: Session = Depends(get_db)):
    q = db.query(Cliente).filter(Cliente.ativo == True)
    if busca:
        termo = f"%{busca}%"
        q = q.filter(
            Cliente.razao_social.ilike(termo) | Cliente.cnpj.ilike(termo)
        )
    clientes = q.order_by(Cliente.razao_social).all()
    return {"data": [ClienteResponse.model_validate(c) for c in clientes], "error": None}


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def criar_cliente(payload: ClienteCreate, db: Session = Depends(get_db)):
    cliente = Cliente(**payload.model_dump())
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return {"data": ClienteResponse.model_validate(cliente), "error": None}


@router.get("/{cliente_id}", response_model=dict)
def obter_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    return {"data": ClienteResponse.model_validate(cliente), "error": None}


@router.put("/{cliente_id}", response_model=dict)
def atualizar_cliente(cliente_id: int, payload: ClienteUpdate, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(cliente, campo, valor)
    db.commit()
    db.refresh(cliente)
    return {"data": ClienteResponse.model_validate(cliente), "error": None}


@router.delete("/{cliente_id}", response_model=dict)
def excluir_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    cliente.ativo = False
    db.commit()
    return {"data": {"excluido": True}, "error": None}
