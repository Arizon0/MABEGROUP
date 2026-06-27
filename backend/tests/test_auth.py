"""Testes de autenticação: login, /me e proteção dos endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.seed import seed_admin
from app.services.auth import hash_senha, verificar_senha


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_hash_e_verificacao_de_senha():
    h = hash_senha("segredo123")
    assert h != "segredo123"
    assert verificar_senha("segredo123", h)
    assert not verificar_senha("errada", h)


@pytest.mark.realauth
def test_login_sucesso_e_me(client, db):
    seed_admin(db)
    resp = client.post(
        "/api/auth/login",
        json={"email": "admin@erp.local", "senha": "admin123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["usuario"]["email"] == "admin@erp.local"
    token = body["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "admin@erp.local"


@pytest.mark.realauth
def test_login_senha_errada(client, db):
    seed_admin(db)
    resp = client.post(
        "/api/auth/login",
        json={"email": "admin@erp.local", "senha": "xxx"},
    )
    assert resp.status_code == 401


@pytest.mark.realauth
def test_endpoint_protegido_sem_token(client, db):
    # Sem Authorization -> 401.
    assert client.get("/api/dashboard").status_code == 401


@pytest.mark.realauth
def test_endpoint_protegido_com_token(client, db):
    seed_admin(db)
    login = client.post(
        "/api/auth/login",
        json={"email": "admin@erp.local", "senha": "admin123"},
    ).json()
    token = login["access_token"]
    resp = client.get(
        "/api/dashboard", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200


@pytest.mark.realauth
def test_health_aberto(client):
    # /health não exige token.
    assert client.get("/health").status_code == 200
