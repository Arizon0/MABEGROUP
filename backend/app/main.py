"""Aplicação FastAPI do ERP Multicanal."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS, DATABASE_URL

log = logging.getLogger(__name__)


def _init_db() -> None:
    """Cria tabelas e seed na primeira execução (idempotente, seguro de re-executar)."""
    try:
        import app.models  # noqa: F401 — registra todos os models no metadata
        from app.database import SessionLocal, engine
        from app.models.base import Base
        from app.seed import seed_admin, seed_locais, seed_sku_map

        Base.metadata.create_all(bind=engine)

        db = SessionLocal()
        try:
            seed_locais(db)
            seed_sku_map(db)
            seed_admin(db)
        finally:
            db.close()

        log.info("_init_db: schema e seed OK")
    except Exception as exc:
        log.warning("_init_db falhou: %s", exc)


# Em produção (PostgreSQL) inicializa na importação do módulo — isso garante
# que as tabelas existam antes do primeiro request, inclusive no cold start do
# Vercel (que importa api/index.py → app.main antes de processar requests).
# Em SQLite (dev/testes) usamos o banco que cada fixture já configura.
if not DATABASE_URL.startswith("sqlite"):
    _init_db()


from app.routers import (  # noqa: E402
    admin,
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

_libera_tudo = "*" in CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _libera_tudo else CORS_ORIGINS,
    allow_credentials=not _libera_tudo,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
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
