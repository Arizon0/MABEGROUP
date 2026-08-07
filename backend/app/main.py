"""Aplicação FastAPI do ERP Multicanal."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import CORS_ORIGINS, DATABASE_URL

log = logging.getLogger(__name__)


def _ensure_colunas_dre(engine) -> None:
    """Adiciona colunas do módulo DRE em bancos criados antes da migration.

    Em produção o schema é materializado por ``create_all()``, que cria tabelas
    novas (ex.: ``dre_despesas``) mas **não altera** tabelas já existentes.
    Estas ALTERs idempotentes garantem as colunas de CMV (vendas) e de gestão
    (produtos) sem depender de rodar o Alembic no deploy serverless.

    Só executa em Postgres (usa ``ADD COLUMN IF NOT EXISTS``); em SQLite as
    tabelas são sempre recriadas por ``create_all`` com o schema atual.
    """
    if engine.dialect.name != "postgresql":
        return
    from sqlalchemy import text

    comandos = (
        "ALTER TABLE vendas ADD COLUMN IF NOT EXISTS custo_unitario NUMERIC(12,4) NOT NULL DEFAULT 0",
        "ALTER TABLE vendas ADD COLUMN IF NOT EXISTS cmv NUMERIC(12,2) NOT NULL DEFAULT 0",
        "ALTER TABLE produtos ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE produtos ADD COLUMN IF NOT EXISTS observacoes VARCHAR(2048)",
    )
    with engine.begin() as conn:
        for comando in comandos:
            conn.execute(text(comando))


def _init_db() -> None:
    """Cria tabelas e seed na primeira execução (idempotente, seguro de re-executar)."""
    try:
        import app.models  # noqa: F401 — registra todos os models no metadata
        from app.database import SessionLocal, engine
        from app.models.base import Base
        from app.seed import seed_admin, seed_catalogo, seed_locais, seed_sku_map

        Base.metadata.create_all(bind=engine)
        _ensure_colunas_dre(engine)

        db = SessionLocal()
        try:
            seed_locais(db)
            seed_sku_map(db)
            seed_catalogo(db)
            seed_admin(db)
        finally:
            db.close()

        log.info("_init_db: schema e seed OK")
    except Exception as exc:
        log.warning("_init_db falhou: %s", exc)


# Inicializa o schema + seed quando:
#  - o banco é PostgreSQL (produção serverless: garante tabelas no cold start), ou
#  - INIT_DB=1 (execução standalone/Docker, inclusive com SQLite).
# Em testes (SQLite, sem INIT_DB) cada fixture cria o próprio schema.
if os.getenv("INIT_DB") == "1" or not DATABASE_URL.startswith("sqlite"):
    _init_db()


from app.routers import (  # noqa: E402
    admin,
    compras,
    dashboard,
    dre,
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
app.include_router(dre.router)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok"}


def _resolver_static_dir() -> Path | None:
    """Localiza a pasta do frontend compilado (``frontend/dist``), se existir."""
    candidatos = []
    env_dir = os.getenv("STATIC_DIR")
    if env_dir:
        candidatos.append(Path(env_dir))
    aqui = Path(__file__).resolve()
    # backend/app/main.py -> raiz do repo é 3 níveis acima
    candidatos.append(aqui.parents[2] / "frontend" / "dist")
    candidatos.append(Path("/app/frontend/dist"))
    for c in candidatos:
        if c.is_dir() and (c / "index.html").is_file():
            return c
    return None


def _montar_frontend(app: FastAPI) -> None:
    """Serve o SPA (React/Vite) pelo próprio backend — app roda como 1 serviço.

    Só monta se ``frontend/dist`` existir (produção/Docker). Em dev/testes, onde
    o build não está presente, não faz nada — a API continua igual.
    """
    dist = _resolver_static_dir()
    if dist is None:
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str):
        # Rotas de API/infra nunca caem aqui (routers registrados antes); mas se
        # um /api/* inexistente chegar, devolve 404 em vez do index.
        if caminho.startswith(("api/", "health")):
            raise HTTPException(status_code=404, detail="Not Found")
        arquivo = dist / caminho
        if arquivo.is_file():
            return FileResponse(str(arquivo))
        return FileResponse(str(dist / "index.html"))

    log.info("Frontend servido de %s", dist)


_montar_frontend(app)
