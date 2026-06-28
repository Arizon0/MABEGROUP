"""Fixtures de teste: banco SQLite em memória + sessão + bypass de auth."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (garante que todas as tabelas entrem no metadata)
from app.main import app
from app.models.base import Base
from app.models.usuario import Usuario
from app.services.auth import get_current_user


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "realauth: não aplicar o bypass de auth (testa o fluxo real de login)",
    )


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


@pytest.fixture(autouse=True)
def _auth_bypass(request):
    """Injeta um usuário autenticado em todos os testes de endpoint.

    Testes marcados com ``@pytest.mark.realauth`` ficam de fora e exercitam o
    fluxo real de login/token.
    """
    if "realauth" in request.keywords:
        yield
        return
    fake = Usuario(
        id=1,
        email="teste@erp.local",
        nome="Teste",
        senha_hash="x",
        perfil="admin",
        ativo=True,
    )
    app.dependency_overrides[get_current_user] = lambda: fake
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)
