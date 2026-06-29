"""Fixtures de teste: banco SQLite em memória + sessão."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (garante que todas as tabelas entrem no metadata)
from app.models.base import Base


@pytest.fixture()
def db() -> Session:
    """Sessão isolada sobre SQLite em memória, com schema criado pelos models."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, future=True)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
