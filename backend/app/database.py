"""Engine, sessão e dependência de banco do FastAPI."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import DATABASE_URL

_is_sqlite = DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

# pool_pre_ping evita erros com conexões derrubadas pelo Postgres gerenciado
# (Supabase) após ociosidade — importante em ambiente serverless (Vercel).
engine = create_engine(
    DATABASE_URL,
    future=True,
    connect_args=_connect_args,
    pool_pre_ping=not _is_sqlite,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """Dependência FastAPI: fornece uma sessão por request e a fecha ao final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
