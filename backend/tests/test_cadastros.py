"""Testes de API do cadastro de Produtos e Fornecedores (Prioridade 2)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app

CNPJ_1 = "11.222.333/0001-81"
CNPJ_2 = "11.222.333/0002-62"


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Fornecedores                                                                  #
# --------------------------------------------------------------------------- #


def test_criar_fornecedor_com_contatos(client):
    resp = client.post(
        "/api/fornecedores",
        json={
            "cnpj": CNPJ_1,
            "razao_social": "Auto Peças Brasil LTDA",
            "nome_fantasia": "AutoBR",
            "uf": "SP",
            "condicoes_pagamento_dias": 30,
            "contatos": [
                {"nome": "João", "cargo": "Comprador", "email": "joao@autobr.com"},
                {"nome": "Maria", "cargo": "Financeiro"},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["cnpj"] == "11222333000181"  # normalizado
    assert len(body["contatos"]) == 2


def test_cnpj_invalido_rejeitado(client):
    resp = client.post(
        "/api/fornecedores",
        json={"cnpj": "11.222.333/0001-82", "razao_social": "Inválida"},
    )
    assert resp.status_code == 422
    assert "CNPJ inválido" in resp.text


def test_cnpj_duplicado(client):
    payload = {"cnpj": CNPJ_1, "razao_social": "Fornecedor X"}
    assert client.post("/api/fornecedores", json=payload).status_code == 201
    resp = client.post("/api/fornecedores", json=payload)
    assert resp.status_code == 409


def test_listar_e_buscar_fornecedor(client):
    client.post("/api/fornecedores", json={"cnpj": CNPJ_1, "razao_social": "Alfa Peças"})
    client.post("/api/fornecedores", json={"cnpj": CNPJ_2, "razao_social": "Beta Peças"})

    todos = client.get("/api/fornecedores").json()
    assert len(todos) == 2

    so_alfa = client.get("/api/fornecedores", params={"q": "Alfa"}).json()
    assert len(so_alfa) == 1
    assert so_alfa[0]["razao_social"] == "Alfa Peças"


# --------------------------------------------------------------------------- #
# Produtos                                                                       #
# --------------------------------------------------------------------------- #


def test_criar_produto_completo(client):
    forn = client.post(
        "/api/fornecedores", json={"cnpj": CNPJ_1, "razao_social": "Fornecedor"}
    ).json()

    resp = client.post(
        "/api/produtos",
        json={
            "sku_base": "5338",
            "nome": "Retentor Volante",
            "categoria": "Retentores",
            "subcategoria": "Volante",
            "atributos": {"material": "borracha", "diametro_mm": 80},
            "unidade_medida": "PC",
            "peso_kg": "0.050",
            "ncm": "84842000",
            "aliquota_icms": "18.00",
            "estoque_minimo": "10",
            "preco_compra": "5.50",
            "preco_venda": "29.90",
            "fornecedor_padrao_id": forn["id"],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["sku_base"] == "5338"
    assert body["atributos"]["diametro_mm"] == 80
    assert body["fornecedor_padrao_id"] == forn["id"]


def test_sku_base_duplicado(client):
    p = {"sku_base": "5338", "nome": "A"}
    assert client.post("/api/produtos", json=p).status_code == 201
    assert client.post("/api/produtos", json=p).status_code == 409


def test_fornecedor_inexistente_no_produto(client):
    resp = client.post(
        "/api/produtos",
        json={"sku_base": "9999", "nome": "X", "fornecedor_padrao_id": 999},
    )
    assert resp.status_code == 422


def test_variantes_de_produto(client):
    pai = client.post(
        "/api/produtos", json={"sku_base": "8126", "nome": "Jogo Anel"}
    ).json()
    var = client.post(
        "/api/produtos",
        json={"sku_base": "8126STD", "nome": "Jogo Anel STD", "produto_pai_id": pai["id"]},
    )
    assert var.status_code == 201

    detalhe = client.get(f"/api/produtos/{pai['id']}").json()
    assert len(detalhe["variantes"]) == 1
    assert detalhe["variantes"][0]["sku_base"] == "8126STD"

    # apenas_pais exclui a variante
    pais = client.get("/api/produtos", params={"apenas_pais": True}).json()
    skus = {p["sku_base"] for p in pais}
    assert "8126" in skus and "8126STD" not in skus


def test_atualizar_produto(client):
    p = client.post("/api/produtos", json={"sku_base": "5245", "nome": "Retentor"}).json()
    resp = client.put(
        f"/api/produtos/{p['id']}", json={"preco_venda": "70.10", "estoque_minimo": "5"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["preco_venda"] == "70.10"
    assert body["nome"] == "Retentor"  # não sobrescrito


def test_produto_nao_pode_ser_variante_de_si_mesmo(client):
    p = client.post("/api/produtos", json={"sku_base": "1", "nome": "X"}).json()
    resp = client.put(f"/api/produtos/{p['id']}", json={"produto_pai_id": p["id"]})
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# Anexos                                                                         #
# --------------------------------------------------------------------------- #


def test_anexos_limite_5(client, tmp_path, monkeypatch):
    # Redireciona o diretório de upload para o tmp do teste.
    import app.services.anexos as anexos_mod

    monkeypatch.setattr(anexos_mod, "UPLOAD_DIR", str(tmp_path))

    p = client.post("/api/produtos", json={"sku_base": "7224", "nome": "Anéis"}).json()

    for i in range(5):
        r = client.post(
            f"/api/produtos/{p['id']}/anexos",
            files={"arquivo": (f"doc{i}.pdf", b"conteudo", "application/pdf")},
            data={"categoria": "ficha_tecnica"},
        )
        assert r.status_code == 201, r.text

    # 6º anexo deve falhar
    r6 = client.post(
        f"/api/produtos/{p['id']}/anexos",
        files={"arquivo": ("doc6.pdf", b"x", "application/pdf")},
    )
    assert r6.status_code == 422
    assert "Limite de 5" in r6.text

    anexos = client.get(f"/api/produtos/{p['id']}/anexos").json()
    assert len(anexos) == 5
