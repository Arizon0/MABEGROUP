"""Endpoint de inicialização do banco (uso único, protegido por token).

Necessário porque o deploy serverless não roda migrations/seed. Chamado uma vez
após o deploy: cria as tabelas, ativa RLS (trava a API pública do Supabase) e
carrega o seed (admin + locais + de-para). Idempotente.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import text

import app.models  # noqa: F401  (garante todas as tabelas no metadata)
from app.config import SETUP_TOKEN
from app.database import SessionLocal, engine
from app.models.base import Base
from app.seed import seed_admin, seed_locais, seed_sku_map

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/setup")
def setup(x_setup_token: str = Header(default="")):
    """Cria o schema, ativa RLS e roda o seed. Requer o header X-Setup-Token."""
    if not SETUP_TOKEN or x_setup_token != SETUP_TOKEN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Token de setup inválido")

    # 1) Cria as tabelas que ainda não existirem (idempotente).
    Base.metadata.create_all(bind=engine)

    # 2) Em Postgres, ativa RLS em todas as tabelas (sem política = API pública
    #    do Supabase bloqueada; o app conecta como 'postgres' e ignora o RLS).
    rls = 0
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            for table in Base.metadata.sorted_tables:
                conn.execute(
                    text(f'ALTER TABLE public."{table.name}" ENABLE ROW LEVEL SECURITY')
                )
                rls += 1

    # 3) Seed (idempotente).
    db = SessionLocal()
    try:
        r_admin = seed_admin(db)
        r_locais = seed_locais(db)
        r_sku = seed_sku_map(db)
    finally:
        db.close()

    return {
        "schema": "ok",
        "rls_tabelas": rls,
        **r_admin,
        **r_locais,
        **r_sku,
    }
