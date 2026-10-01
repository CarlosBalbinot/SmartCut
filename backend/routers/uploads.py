from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from middleware.permissions import get_current_user
from models.usuario import Permissao, Usuario
from services.pasta_dados import pasta_uploads

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])

# Pastas de upload com acesso restrito por permissão granular: os XMLs de
# NF-e são documentos fiscais assinados — só quem tem permissão fiscal
# (fiscal_nfe/ver) pode baixá-los por aqui (item 2.1).
_RESTRICOES_POR_PASTA = {"nfe": ("fiscal_nfe", "ver")}


def _tem_permissao(db: Session, usuario: Usuario, modulo: str, acao: str) -> bool:
    """Administradores passam sempre; os demais precisam da permissão exata."""
    if usuario.is_admin:
        return True
    return (
        db.query(Permissao)
        .filter(
            Permissao.usuario_id == usuario.id,
            Permissao.modulo == modulo,
            Permissao.acao == acao,
            Permissao.permitido == True,  # noqa: E712 — expressão SQL
        )
        .first()
        is not None
    )


@router.get("/{caminho:path}")
def baixar_arquivo(
    caminho: str,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serve um arquivo de <pasta de dados>/uploads com autenticação e autorização.

    Substitui o antigo `app.mount("/uploads", StaticFiles(...))`, que era
    público — qualquer pessoa na rede baixava XMLs de NF-e. Aqui:
    - qualquer download exige usuário do sistema administrativo (token JWT
      por header ou cookie HttpOnly);
    - pastas sensíveis (nfe/) exige permissão fiscal correspondente;
    - path traversal (.. ou separadores alternados) é bloqueado com 403;
    - arquivos inexistentes ou diretórios retornam 404.
    """
    caminho_decodificado = unquote(caminho)
    raiz = pasta_uploads().resolve()
    # Decodifica percent-encoding (ex.: "%2e%2e" => "..") caso o framework
    # entregue o segmento cru — a contenção abaixo funciona com o texto real.
    alvo = (raiz / caminho_decodificado).resolve()

    # Bloqueia path traversal: o arquivo precisa estar dentro de uploads/.
    if raiz != alvo and raiz not in alvo.parents:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caminho inválido",
        )

    # Restrição granular por módulo (NF-e = documento fiscal assinado).
    primeiro_segmento = caminho_decodificado.replace("\\", "/").split("/", 1)[0].lower()
    restricao = _RESTRICOES_POR_PASTA.get(primeiro_segmento)
    if restricao and not _tem_permissao(db, current_user, *restricao):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para acessar este arquivo",
        )

    if not alvo.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo não encontrado",
        )

    return FileResponse(str(alvo))
