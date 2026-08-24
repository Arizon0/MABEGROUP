"""Aplicação FastAPI do ERP Multicanal."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import CORS_ORIGINS, DATABASE_URL, validar_configuracao

log = logging.getLogger(__name__)


def _ensure_colunas(engine) -> None:
    """Adiciona colunas novas em bancos criados antes das migrations.

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
        "ALTER TABLE vendas ADD COLUMN IF NOT EXISTS numero_nf VARCHAR(30)",
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
        from app.seed import (
            seed_admin,
            seed_catalogo,
            seed_locais,
            seed_sku_map,
            seed_usuarios,
        )

        Base.metadata.create_all(bind=engine)
        _ensure_colunas(engine)

        db = SessionLocal()
        try:
            seed_locais(db)
            seed_sku_map(db)
            seed_catalogo(db)
            seed_admin(db)
            seed_usuarios(db)
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
    auth,
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
    usuarios,
    vendas,
)

from app.services.permissoes import autorizar_escrita  # noqa: E402

# Aborta o boot se a app estiver indo para produção com segredo de exemplo.
for _aviso in validar_configuracao():
    log.warning("configuração: %s", _aviso)

app = FastAPI(title="ERP Multicanal — Marketplace", version="0.1.0")

_libera_tudo = "*" in CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _libera_tudo else CORS_ORIGINS,
    allow_credentials=not _libera_tudo,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Rotas públicas ---------------------------------------------------------
# ``auth`` precisa ser alcançável sem token (é onde o token nasce) e ``admin``
# tem a própria trava, o SETUP_TOKEN — é o bootstrap que roda antes de existir
# qualquer usuário para autenticar.
app.include_router(auth.router)
app.include_router(admin.router)

# --- Rotas protegidas -------------------------------------------------------
# A exigência de token é declarada **no include**, não endpoint a endpoint: um
# endpoint novo entra protegido por padrão, e esquecer a dependência deixa de
# ser uma forma de vazar dado financeiro. Todo endpoint abaixo responde 401 sem
# um ``Authorization: Bearer`` válido.
# ``autorizar_escrita`` já depende de ``get_current_user``, então cobre a
# autenticação e, de quebra, barra o perfil de leitura em qualquer método
# que altere dados.
PROTEGIDO = [Depends(autorizar_escrita)]

for _router in (
    importar.router,
    sku_map.router,
    produtos.router,
    fornecedores.router,
    estoque.router,
    compras.router,
    dashboard.router,
    financeiro.router,
    relatorios.router,
    dre.router,
    vendas.router,
):
    app.include_router(_router, dependencies=PROTEGIDO)

# Cadastro de usuários: o próprio router já exige perfil admin, que por sua
# vez depende de get_current_user — então token continua obrigatório.
app.include_router(usuarios.router)


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
