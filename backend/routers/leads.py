import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models.painel_vendedor import Lead

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


@router.get("/")
def listar(db: Session = Depends(get_db)):
    rows = db.execute(select(Lead).order_by(Lead.criado_em.desc())).scalars().all()
    return {
        "data": [
            {
                "id": str(lead.id),
                "vendedor_id": str(lead.vendedor_id),
                "nome": lead.nome,
                "segmento": lead.segmento,
                "endereco": lead.endereco,
                "cidade": lead.cidade,
                "telefone": lead.telefone,
                "observacao": lead.observacao,
                "status": lead.status,
                "criado_em": lead.criado_em.isoformat() if lead.criado_em else None,
            }
            for lead in rows
        ],
        "error": None,
    }


class LeadCreate(BaseModel):
    vendedor_id: uuid.UUID
    nome: str
    segmento: Optional[str] = None
    endereco: Optional[str] = None
    cidade: Optional[str] = None
    telefone: Optional[str] = None
    observacao: Optional[str] = None


@router.post("/")
def criar(payload: LeadCreate, db: Session = Depends(get_db)):
    lead = Lead(**payload.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return {"data": {"id": str(lead.id), "nome": lead.nome, "status": lead.status}, "error": None}


@router.delete("/{lead_id}")
def deletar(lead_id: uuid.UUID, db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    db.delete(lead)
    db.commit()
    return {"data": None, "error": None}
