import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings

# Logger de erro do servidor: o uvicorn configura handlers para ele, então a
# exceção completa vai para o log (item 2.5).
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Item 5.2: o schema é governado por migrações Alembic versionadas —
    # `Base.metadata.create_all` deixou de existir no boot (ele criava
    # tabelas novas mas nunca alterava tabelas existentes). Bancos criados
    # na era do create_all são registrados na baseline (stamp head) e bancos
    # novos seguem upgrade head.
    from services.db_migracoes import aplicar_migracoes

    aplicar_migracoes()

    # Item 4.2: migra senhas de certificado armazenadas no formato antigo
    # (base64 reversível) para o envelope cifrado, quando houver chave ativa.
    # Sem chave não faz nada — valores legados seguem usáveis em leitura.
    from database import SessionLocal
    from services.segredo_service import migrar_segredos_legados
    from services.usuario_service import sincronizar_permissoes_fiscais

    try:
        db = SessionLocal()
        try:
            migrados = migrar_segredos_legados(db)
            # Item 5.1: quem já tinha `ver` nos módulos de execução fiscal
            # continua podendo executar (a ação correta é garantida no boot).
            perms_extra = sincronizar_permissoes_fiscais(db)
        finally:
            db.close()
        if migrados:
            logger.info("[segredos] migradas %d senha(s) de certificado para o formato cifrado", migrados)
        if perms_extra:
            logger.info("[permissoes] %d permissão(ões) fiscais de execução adicionadas no boot", perms_extra)
    except Exception as err:  # noqa: BLE001 — nunca impede o boot
        logger.warning("[segredos/permissoes] aviso no boot: %s", err)

    # Item 3.3: backup automático do SQLite (thread daemon; só atua quando o
    # banco é SQLite). Para no shutdown.
    from services.backup_service import iniciar_backup_automatico, parar_backup_automatico

    iniciar_backup_automatico()
    try:
        yield
    finally:
        parar_backup_automatico()

from routers import encaixes, grupos_molde, moldes
from routers import modelos_tecido, cores_tecido, lotes_tecido
from routers import precificacoes
from routers import (
    configuracao_empresa,
    tabelas_preco,
    grupos_preco,
    vendedores,
    pedidos_venda,
    auth,
    vendedor_painel,
    catalogos,
    leads,
)
from routers import financeiro
from routers import dashboard
from routers import clientes
from routers import produtos
from routers import transportadoras
from routers import usuarios
from routers import tes
from routers import nfe
from routers import condicoes_pagamento
from routers import tabelas_grade
from routers import configuracao_grade
from routers import uploads

app = FastAPI(
    title="SmartCut API",
    description="Sistema inteligente de gestão e otimização de corte têxtil",
    version="0.1.0",
    lifespan=lifespan,
)

# Item 2.4: além do navegador em dev (Vite em http://localhost:5173), o
# Electron empacotado carrega o frontend pelo protocolo próprio app://bundle
# (item 2.2) — ambas as origens precisam passar no CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "app://bundle"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers legados ───────────────────────────────────────────────────
app.include_router(moldes.router)
app.include_router(grupos_molde.router)
app.include_router(encaixes.router)

# ── Routers nova hierarquia de tecidos ────────────────────────────────
app.include_router(modelos_tecido.router)
app.include_router(cores_tecido.router)
app.include_router(lotes_tecido.router)

# ── Precificação ──────────────────────────────────────────────────────
app.include_router(precificacoes.router)

# ── Vendas ────────────────────────────────────────────────────────────
app.include_router(configuracao_empresa.router)
app.include_router(tabelas_preco.router)
app.include_router(grupos_preco.router)
app.include_router(vendedores.router)
app.include_router(pedidos_venda.router)

# ── Auth ──────────────────────────────────────────────────────────────
app.include_router(auth.router)

# ── Painel do vendedor ────────────────────────────────────────────────
app.include_router(vendedor_painel.router)

# ── Catálogos e Leads ─────────────────────────────────────────────────
app.include_router(catalogos.router)
app.include_router(leads.router)

# ── Financeiro ────────────────────────────────────────────────────────────────
app.include_router(financeiro.router)

# ── Dashboard ─────────────────────────────────────────────────────────────────
app.include_router(dashboard.router)

# ── Clientes ──────────────────────────────────────────────────────────────────
app.include_router(clientes.router)

# ── Produtos ──────────────────────────────────────────────────────────────────
app.include_router(produtos.router)
app.include_router(produtos.grupos_router)
app.include_router(produtos.linhas_grade_router)
app.include_router(produtos.colunas_grade_router)

# ── Transportadoras ─────────────────────────────────────────────────────────
app.include_router(transportadoras.router)

# ── Auth administrativo e Usuários ───────────────────────────────────────────
app.include_router(auth.router_admin)
app.include_router(usuarios.router)

# ── Fiscal ────────────────────────────────────────────────────────────────────
app.include_router(tes.router)
app.include_router(nfe.router)

# ── Condições de Pagamento ───────────────────────────────────────────────────
app.include_router(condicoes_pagamento.router)

# ── Tabelas de Grade ──────────────────────────────────────────────────────────
app.include_router(tabelas_grade.router)
app.include_router(configuracao_grade.router)

# ── Uploads autenticados (item 2.1) ───────────────────────────────────────────
app.include_router(uploads.router)


os.makedirs(settings.upload_dir, exist_ok=True)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Item 2.5: o corpo do 500 NUNCA devolve a exceção crua (vazava SQL,
    # paths internos e stack para o cliente via API/OpenAPI). A exceção
    # completa vai para o log do servidor; a resposta é genérica em PT-BR.
    # HTTPException continua indo para o handler padrão do FastAPI — o
    # "detail" só é devolvido para exceções explícitas da aplicação.
    logger.error(
        "Erro interno não tratado em %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"data": None, "error": "Erro interno"},
    )


@app.get("/health")
def health():
    return {"status": "ok"}
