"""Testes de API (FastAPI TestClient) cobrindo importação e SKU map."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.seed import seed_sku_map
from tests.factories import build_ml_xlsx


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_importar_ml_endpoint(client, db, tmp_path):
    seed_sku_map(db)
    path, esperado = build_ml_xlsx(tmp_path / "ml.xlsx")
    with open(path, "rb") as fh:
        resp = client.post(
            "/api/importar/ml",
            files={"arquivo": ("ml.xlsx", fh, "application/vnd.openxmlformats")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["canal"] == "Mercado Livre"
    assert body["totais"]["liquido_recebido"] == str(esperado["liquido_recebido"])
    assert body["skus_pendentes"] == 0


def test_sku_map_listagem_e_pendencias(client, db, tmp_path):
    seed_sku_map(db)
    # importa sem seed de um sku novo -> gera pendência
    path, _ = build_ml_xlsx(tmp_path / "ml.xlsx")
    # remove um mapeamento para forçar pendência (5338)
    from sqlalchemy import delete
    from app.models.sku_map import SkuMap

    db.execute(delete(SkuMap).where(SkuMap.sku_canal == "5338"))
    db.commit()

    with open(path, "rb") as fh:
        client.post("/api/importar/ml", files={"arquivo": ("ml.xlsx", fh, "x")})

    pend = client.get("/api/sku-map/pendencias").json()
    assert any(p["sku_canal"] == "5338" for p in pend)

    # mapeia 5338 -> produto 5338 via sku_base
    resp = client.post(
        "/api/sku-map",
        json={"sku_canal": "5338", "canal": "Mercado Livre", "sku_base": "5338"},
    )
    assert resp.status_code == 200
    assert resp.json()["sku_base"] == "5338"

    # pendência foi removida
    pend2 = client.get("/api/sku-map/pendencias").json()
    assert not any(p["sku_canal"] == "5338" for p in pend2)


def test_busca_produtos(client, db):
    seed_sku_map(db)
    resp = client.get("/api/sku-map/produtos", params={"q": "5338"})
    assert resp.status_code == 200
    produtos = resp.json()
    assert any(p["sku_base"] == "5338" for p in produtos)
