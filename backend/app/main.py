"""Aplicação FastAPI do ERP Multicanal."""
from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.routers import (
    admin,
    auth,
    compras,
    dashboard,
    estoque,
    financeiro,
    fornecedores,
    importar,
    produtos,
    relatorios,
    sku_map,
)
from app.services.auth import get_current_user

app = FastAPI(title="ERP Multicanal — Marketplace", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas abertas (sem token): login e setup inicial (protegido por SETUP_TOKEN).
app.include_router(auth.router)
app.include_router(admin.router)

# Rotas de negócio: exigem usuário autenticado (JWT no header Authorization).
_protegido = [Depends(get_current_user)]
app.include_router(importar.router, dependencies=_protegido)
app.include_router(sku_map.router, dependencies=_protegido)
app.include_router(produtos.router, dependencies=_protegido)
app.include_router(fornecedores.router, dependencies=_protegido)
app.include_router(estoque.router, dependencies=_protegido)
app.include_router(compras.router, dependencies=_protegido)
app.include_router(dashboard.router, dependencies=_protegido)
app.include_router(financeiro.router, dependencies=_protegido)
app.include_router(relatorios.router, dependencies=_protegido)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok"}
