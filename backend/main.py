import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

from routers import encaixes, grupos_molde, moldes, tecidos
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
from routers import clientes

app = FastAPI(
    title="SmartCut API",
    description="Sistema inteligente de gestão e otimização de corte têxtil",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers legados ───────────────────────────────────────────────────
app.include_router(tecidos.router)
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

# ── Clientes ──────────────────────────────────────────────────────────────────
app.include_router(clientes.router)


os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"data": None, "error": str(exc)},
    )


@app.get("/health")
def health():
    return {"status": "ok"}
