"""Fixtures de teste: banco SQLite em memória, sessão e cliente autenticado."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (garante que todas as tabelas entrem no metadata)
from app.config import ADMIN_EMAIL
from app.database import get_db
from app.main import app
from app.models.base import Base
from app.models.usuario import Usuario
from app.seed import seed_admin
from app.services.auth import criar_access_token


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


@pytest.fixture()
def usuario(db) -> Usuario:
    """Administrador criado pelo mesmo caminho do seed de produção."""
    seed_admin(db)
    return db.execute(
        select(Usuario).where(Usuario.email == ADMIN_EMAIL.strip().lower())
    ).scalar_one()


@pytest.fixture()
def token(usuario: Usuario) -> str:
    return criar_access_token(usuario)


@pytest.fixture()
def client_anonimo(db) -> TestClient:
    """Cliente sem token — usado para provar que os endpoints recusam."""
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def client(db, token: str) -> TestClient:
    """Cliente autenticado.

    O token é real e passa pelo mesmo ``get_current_user`` que a API usa em
    produção — nada de sobrescrever a dependência de autenticação, senão os
    testes passariam mesmo que a trava estivesse quebrada.
    """
    app.dependency_overrides[get_db] = lambda: db
    try:
        cliente = TestClient(app)
        cliente.headers["Authorization"] = f"Bearer {token}"
        yield cliente
    finally:
        app.dependency_overrides.clear()
