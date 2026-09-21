import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import require_permission
from models.venda import PrecoReferencia
from schemas.venda_schema import PrecoReferenciaCreate, PrecoReferenciaOut, PrecoReferenciaUpdate

router = APIRouter(prefix="/api/v1/grupos-molde", tags=["grupos_preco"])

# Preços de referência por grupo pertencem ao mesmo domínio de tabelas de
# preço, gerido no painel de Configurações. configuracoes_ver/
# configuracoes_editar são módulos próprios em MODULOS_VALIDOS — a ação
# passada é sempre "ver" (única ação hoje verificada em todo o sistema).
_MOD_VER = "configuracoes_ver"
_MOD_EDITAR = "configuracoes_editar"


@router.get("/{grupo_id}/precos", dependencies=[Depends(require_permission(_MOD_VER, "ver"))])
def listar_precos(grupo_id: uuid.UUID, db: Session = Depends(get_db)):
    rows = db.execute(
        select(PrecoReferencia).where(PrecoReferencia.grupo_id == grupo_id)
    ).scalars().all()
    return {"data": [PrecoReferenciaOut.model_validate(r) for r in rows], "error": None}


@router.post("/{grupo_id}/precos", dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))])
def criar_preco(grupo_id: uuid.UUID, payload: PrecoReferenciaCreate, db: Session = Depends(get_db)):
    existing = db.execute(
        select(PrecoReferencia).where(
            PrecoReferencia.grupo_id == grupo_id,
            PrecoReferencia.tabela_id == payload.tabela_id,
        )
    ).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="Preço já cadastrado para esta tabela")
    ref = PrecoReferencia(
        grupo_id=grupo_id,
        tabela_id=payload.tabela_id,
        preco_avista=payload.preco_avista,
        preco_aprazo=payload.preco_aprazo,
        tem_plus_size=payload.tem_plus_size or False,
        preco_avista_plus=payload.preco_avista_plus,
        preco_aprazo_plus=payload.preco_aprazo_plus,
    )
    db.add(ref)
    db.commit()
    db.refresh(ref)
    return {"data": PrecoReferenciaOut.model_validate(ref), "error": None}


@router.patch(
    "/{grupo_id}/precos/{tabela_id}",
    dependencies=[Depends(require_permission(_MOD_EDITAR, "ver"))],
)
def atualizar_preco(
    grupo_id: uuid.UUID,
    tabela_id: uuid.UUID,
    payload: PrecoReferenciaUpdate,
    db: Session = Depends(get_db),
):
    ref = db.execute(
        select(PrecoReferencia).where(
            PrecoReferencia.grupo_id == grupo_id,
            PrecoReferencia.tabela_id == tabela_id,
        )
    ).scalars().first()
    if not ref:
        raise HTTPException(status_code=404, detail="Preço de referência não encontrado")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(ref, field, val)
    db.commit()
    db.refresh(ref)
    return {"data": PrecoReferenciaOut.model_validate(ref), "error": None}
