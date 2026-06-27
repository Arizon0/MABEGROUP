"""Aplicação FastAPI do ERP Multicanal."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.routers import (
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

app = FastAPI(title="ERP Multicanal — Marketplace", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(importar.router)
app.include_router(sku_map.router)
app.include_router(produtos.router)
app.include_router(fornecedores.router)
app.include_router(estoque.router)
app.include_router(compras.router)
app.include_router(dashboard.router)
app.include_router(financeiro.router)
app.include_router(relatorios.router)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok"}
