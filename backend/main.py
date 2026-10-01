import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.pasta_dados import pasta_uploads

# Item 9.2: logging estruturado (timestamp, nível, módulo, request_id).
from logging_conf import RequestIdMiddleware, instalar_logging, request_id_var

from routers import (
    auth,
    catalogos,
    clientes,
    condicoes_pagamento,
    configuracao_empresa,
    configuracao_grade,
    cores_tecido,
    dashboard,
    encaixes,
    financeiro,
    grupos_molde,
    grupos_preco,
    leads,
    lotes_tecido,
    modelos_tecido,
    moldes,
    nfe,
    ordens_corte,
    pedidos_venda,
    precificacoes,
    produtos,
    relatorios,
    tabelas_grade,
    tabelas_preco,
    tes,
    transportadoras,
    uploads,
    usuarios,
    vendedores,
    vendedor_painel,
)

# Item 9.2: logging estruturado (timestamp, nível, módulo, request_id) ativado
# na importação do app — vale para main, routers, services e o handler 500.
instalar_logging()

# Logger do app: flui para o raiz configurado em instalar_logging() (9.2) —
# a exceção completa (traceback) vai para o log, nunca para a resposta.
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Item 5.2: o schema é governado por migrações Alembic versionadas —
    # `Base.metadata.create_all` deixou de existir no boot (ele criava
    # tabelas novas mas nunca alterava tabelas existentes). Banco novo segue
    # upgrade head; banco com tabelas e sem versão registrada interrompe o
    # boot (services/db_migracoes.py — nunca carimba sem criar a estrutura).
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

    # RL1: pasta de modelos de relatório (<raiz do SmartCut>/relatorios) —
    # só cria o que faltar (pastas e config.json); os modelos são do usuário.
    from services.relatorios.engine import garantir_pasta

    try:
        logger.info("[relatorios] pasta de modelos: %s", garantir_pasta())
    except Exception as err:  # noqa: BLE001 — nunca impede o boot
        logger.warning("[relatorios] aviso no boot: %s", err)

    # Motor de encaixe: exe montado sem spyrrow/ortools aparece aqui e em /health.
    from services import nesting_v2

    (logger.info if nesting_v2.DISPONIVEL else logger.error)("[encaixe] %s", nesting_v2.diagnostico())

    try:
        yield
    finally:
        parar_backup_automatico()


app = FastAPI(
    title="SmartCut API",
    description="Sistema inteligente de gestão e otimização de corte têxtil",
    version="1.3.0",
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

# Item 9.2: request_id por requisição — presente em cada linha de log do
# request (filtro/contextvar) e devolvido no header X-Request-ID da resposta,
# permitindo rastrear um erro de produção reportado pelo usuário.
# Adicionado depois do CORS (é o middleware mais externo).
app.add_middleware(RequestIdMiddleware)

# ── Registro declarativo de routers (item 10.3) ─────────────────────────────
# A ORDEM abaixo é a precedência de rotas do FastAPI (primeiro registro resolve
# primeiro) — NÃO reordenar sem comparar as rotas registradas.
# `eh_legado=True` = módulos da arquitetura antiga (molde/encaixe) mantidos por
# compatibilidade; os demais grupos são a arquitetura atual.
REGISTRO_DE_ROUTERS: list[tuple[str, bool, list[APIRouter]]] = [
    # ("grupo de domínio", eh_legado, [routers...])
    (
        "Legado — moldes/encaixes (arquitetura antiga, mantidos)",
        True,
        [
            moldes.router,
            grupos_molde.router,
            encaixes.router,
        ],
    ),
    (
        "Hierarquia de tecidos",
        False,
        [
            modelos_tecido.router,
            cores_tecido.router,
            lotes_tecido.router,
        ],
    ),
    ("Precificação", False, [precificacoes.router]),
    (
        "Vendas",
        False,
        [
            configuracao_empresa.router,
            tabelas_preco.router,
            grupos_preco.router,
            vendedores.router,
            pedidos_venda.router,
        ],
    ),
    ("Auth", False, [auth.router]),
    ("Painel do vendedor", False, [vendedor_painel.router]),
    ("Catálogos e Leads", False, [catalogos.router, leads.router]),
    ("Financeiro", False, [financeiro.router]),
    ("Dashboard", False, [dashboard.router]),
    ("Clientes", False, [clientes.router]),
    (
        "Produtos e grades",
        False,
        [
            produtos.router,
            produtos.grupos_router,
            produtos.linhas_grade_router,
            produtos.colunas_grade_router,
        ],
    ),
    ("Transportadoras", False, [transportadoras.router]),
    ("Auth administrativo e Usuários", False, [auth.router_admin, usuarios.router]),
    ("Fiscal (TES/NF-e)", False, [tes.router, nfe.router]),
    ("Condições de Pagamento", False, [condicoes_pagamento.router]),
    ("Tabelas de Grade", False, [tabelas_grade.router, configuracao_grade.router]),
    ("Uploads autenticados (item 2.1)", False, [uploads.router]),
    ("Relatórios configuráveis (RL1)", False, [relatorios.router]),
    ("Produção — Ordem de Corte", False, [ordens_corte.router]),
]

for grupo, eh_legado, routers_do_grupo in REGISTRO_DE_ROUTERS:
    if eh_legado:
        logger.info("Registrando routers legados do grupo '%s'", grupo)
    for router in routers_do_grupo:
        app.include_router(router)


# Arquivos do usuário: sempre na pasta de dados (userData no app instalado),
# nunca na pasta do executável — ver services/pasta_dados.py.
logger.info("Pasta de dados do usuário: %s", pasta_uploads().parent)


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
    # O header X-Request-ID (adicionado pelo RequestIdMiddleware) permite ao
    # usuário repassar o id — a mesma linha existe no log com o traceback.
    return JSONResponse(
        status_code=500,
        content={"data": None, "error": "Erro interno"},
        headers={"X-Request-ID": request_id_var.get()},
    )


@app.get("/health")
def health():
    from services import nesting_v2

    return {"status": "ok", "motor_v2_disponivel": nesting_v2.DISPONIVEL}
