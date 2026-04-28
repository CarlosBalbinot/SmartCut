from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import encaixes, grupos_molde, moldes, pedidos, tecidos
from routers import modelos_tecido, cores_tecido, lotes_tecido
from routers import precificacoes

app = FastAPI(
    title="SmartCut API",
    description="Sistema inteligente de gestão e otimização de corte têxtil",
    version="0.1.0",
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
app.include_router(pedidos.router)
app.include_router(moldes.router)
app.include_router(grupos_molde.router)
app.include_router(encaixes.router)

# ── Routers nova hierarquia de tecidos ────────────────────────────────
app.include_router(modelos_tecido.router)
app.include_router(cores_tecido.router)
app.include_router(lotes_tecido.router)

# ── Precificação ──────────────────────────────────────────────────────
app.include_router(precificacoes.router)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"data": None, "error": str(exc)},
    )


@app.get("/health")
def health():
    return {"status": "ok"}
