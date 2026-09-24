import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from models.cliente import Cliente
from schemas.cliente_schema import ClienteCreate, ClienteResponse, ClienteUpdate
from services.venda_service import sincronizar_cliente_pedidos

router = APIRouter(prefix="/api/v1/clientes", tags=["clientes"])

_MOD = "cadastros_clientes"


def _proximo_codigo(db: Session) -> str:
    codigos = [row[0] for row in db.query(Cliente.codigo).filter(Cliente.codigo.isnot(None)).all()]
    max_val = 0
    for codigo in codigos:
        try:
            n = int(codigo)
            if n > max_val:
                max_val = n
        except (ValueError, TypeError):
            pass
    return str(max_val + 1).zfill(4)


# Tipos de registro que podem ser cliente de um pedido (fornecedor puro não).
_TIPOS_CLIENTE = ("cliente", "ambos")


def _digitos(v: str | None) -> str:
    return re.sub(r"\D", "", v or "")


def cliente_lookup_out(c: Cliente) -> dict:
    return {
        "id": c.id,
        "codigo": c.codigo,
        "razao_social": c.razao_social,
        "cnpj": c.cnpj or c.cpf,
        "cidade": c.cidade,
        "uf": c.estado,
    }


def buscar_cliente_por_codigo_ou_documento(db: Session, valor: str) -> Cliente | None:
    """Código do cliente ou CNPJ/CPF (pontuação ignorada). 11 ou 14 dígitos
    = documento; qualquer outra coisa = código ("1" também acha "0001").
    Só clientes ativos do tipo cliente/ambos."""
    texto = (valor or "").strip().upper()
    digitos = _digitos(texto)
    if not texto:
        return None
    base = db.query(Cliente).filter(
        Cliente.ativo == True,  # noqa: E712
        Cliente.tipo_registro.in_(_TIPOS_CLIENTE),
    )

    if len(digitos) in (11, 14):
        # Documento pode estar gravado com ou sem pontuação — compara dígitos.
        for c in base.filter(Cliente.cnpj.isnot(None) | Cliente.cpf.isnot(None)).all():
            if digitos in (_digitos(c.cnpj), _digitos(c.cpf)):
                return c

    cliente = base.filter(Cliente.codigo == texto).first()
    if cliente is None and texto.isdigit():
        for c in base.filter(Cliente.codigo.isnot(None)).all():
            if c.codigo.isdigit() and int(c.codigo) == int(texto):
                return c
    return cliente


@router.get("/validar", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def validar_cliente(codigo: str, db: Session = Depends(get_db)):
    """Lookup do campo Cliente do pedido: código ou CNPJ/CPF."""
    cliente = buscar_cliente_por_codigo_ou_documento(db, codigo)
    if not cliente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    return {"data": cliente_lookup_out(cliente), "error": None}


@router.get("/cnpj/{cnpj}", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def buscar_por_cnpj(cnpj: str, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.cnpj == cnpj, Cliente.ativo == True).first()  # noqa: E712 — expressão SQL
    if not cliente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    return {"data": ClienteResponse.model_validate(cliente), "error": None}


@router.get("/", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def listar_clientes(
    busca: str = "",
    tipo: str | None = None,
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """busca: razão social, fantasia, código, CNPJ/CPF (com ou sem pontuação)
    ou cidade. limit/offset opcionais — sem limit devolve tudo (tela de
    Clientes); o modal de busca do pedido pagina de 50 em 50."""
    q = db.query(Cliente).filter(Cliente.ativo == True)  # noqa: E712 — expressão SQL
    # tipo=cliente inclui "ambos" (quem pode ser cliente de pedido); os
    # demais tipos filtram exato. Filtro no SQL, antes do limit/offset.
    if tipo == "cliente":
        q = q.filter(Cliente.tipo_registro.in_(_TIPOS_CLIENTE))
    elif tipo:
        q = q.filter(Cliente.tipo_registro == tipo)
    if busca:
        termo = f"%{busca.strip()}%"
        filtro = (
            Cliente.razao_social.ilike(termo)
            | Cliente.nome_fantasia.ilike(termo)
            | Cliente.codigo.ilike(termo)
            | Cliente.cidade.ilike(termo)
            | Cliente.cnpj.ilike(termo)
            | Cliente.cpf.ilike(termo)
        )
        digitos = _digitos(busca)
        if len(digitos) >= 3:
            filtro = filtro | Cliente.cnpj.ilike(f"%{digitos}%") | Cliente.cpf.ilike(f"%{digitos}%")
        q = q.filter(filtro)
    q = q.order_by(Cliente.razao_social)
    if limit:
        q = q.offset(offset).limit(limit)
    clientes = q.all()
    return {"data": [ClienteResponse.model_validate(c) for c in clientes], "error": None}


@router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(_MOD, "criar"))],
)
def criar_cliente(payload: ClienteCreate, db: Session = Depends(get_db)):
    cliente = Cliente(codigo=_proximo_codigo(db), **payload.model_dump())
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return {"data": ClienteResponse.model_validate(cliente), "error": None}


@router.get("/{cliente_id}", response_model=dict, dependencies=[Depends(require_permission(_MOD, "ver"))])
def obter_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    return {"data": ClienteResponse.model_validate(cliente), "error": None}


@router.put(
    "/{cliente_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "editar"))],
)
def atualizar_cliente(cliente_id: int, payload: ClienteUpdate, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(cliente, campo, valor)
    # Mesma transação: a cópia cliente_* dos pedidos Abertos e sem NF-e
    # acompanha o cadastro (ex.: IBGE corrigido chega à NF-e do pedido).
    db.flush()
    sincronizados = sincronizar_cliente_pedidos(db, cliente.id)
    db.commit()
    db.refresh(cliente)
    data = ClienteResponse.model_validate(cliente).model_dump()
    data["pedidos_sincronizados"] = sincronizados
    return {"data": data, "error": None}


@router.delete(
    "/{cliente_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(_MOD, "excluir"))],
)
def excluir_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    cliente.ativo = False
    db.commit()
    return {"data": {"excluido": True}, "error": None}
