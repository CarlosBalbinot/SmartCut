"""Relatórios configuráveis (RL1) — ver services/relatorios/engine.py.

Os modelos ficam na pasta relatorios/ do SmartCut, editada pelo Explorer;
a API só lê:

GET /relatorios/{codigo}/variantes            [{arquivo, padrao}]
GET /relatorios/{codigo}/html?id=&variante=   HTML renderizado
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import get_current_user, require_permission
from models.usuario import Usuario
from services.relatorios import engine

router = APIRouter(prefix="/api/v1/relatorios", tags=["relatorios"])


def _exigir_permissao(codigo: str, usuario: Usuario, db: Session) -> None:
    rel = engine.REGISTRO.get(codigo)
    if rel is None:
        raise HTTPException(status_code=404, detail=f"Relatório {codigo} não existe.")
    # Permissão do relatório (ex.: relVen001 → pedidos_ver): mesma checagem
    # do require_permission, com o módulo vindo do registro.
    require_permission(rel.permissao, "ver")(current_user=usuario, db=db)


@router.get("/{codigo}/variantes")
def variantes(
    codigo: str,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _exigir_permissao(codigo, usuario, db)
    return {"data": engine.variantes(codigo), "error": None}


@router.get("/{codigo}/html", response_class=HTMLResponse)
def html(
    codigo: str,
    id: str,
    variante: str | None = None,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _exigir_permissao(codigo, usuario, db)
    try:
        conteudo = engine.renderizar(db, codigo, id, variante)
    except engine.ErroRelatorio as exc:
        raise HTTPException(status_code=exc.status, detail=exc.mensagem)
    except engine.ErroModelo as exc:
        # 422 com arquivo/linha para o usuário corrigir o modelo.
        return JSONResponse(
            status_code=422,
            content={
                "data": None,
                "error": exc.texto(),
                "modelo": {"arquivo": exc.arquivo, "linha": exc.linha, "mensagem": exc.mensagem},
            },
        )
    return HTMLResponse(conteudo)
