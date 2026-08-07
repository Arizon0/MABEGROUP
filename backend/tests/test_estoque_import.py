"""Testes da importação de estoque atual via planilha."""
from __future__ import annotations

import io
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.estoque import LOCAL_GALPAO, EstoqueSaldo, Local
from app.models.produto import Produto
from app.services import estoque as svc
from app.services.estoque_import import importar_estoque, parse_estoque


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def cenario(db):
    db.add_all([
        Produto(sku_base="5338", nome="Retentor", preco_compra=Decimal("6.50")),
        Produto(sku_base="8126", nome="Anel", preco_compra=Decimal("10.00")),
    ])
    db.add(Local(nome="Galpão Central", tipo=LOCAL_GALPAO))
    db.flush()
    return db


def _planilha(linhas: list[dict]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    cabecalho = list(linhas[0].keys())
    ws.append(cabecalho)
    for reg in linhas:
        ws.append([reg[c] for c in cabecalho])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_estoque_detecta_colunas():
    linhas = parse_estoque([
        {"SKU": "5338", "Quantidade": "10", "Custo": "6,50"},
        {"SKU": "8126", "Quantidade": 4, "Custo": ""},
    ])
    assert len(linhas) == 2
    assert linhas[0].sku_texto == "5338"
    assert linhas[0].qtd == Decimal("10")
    assert linhas[0].custo == Decimal("6.50")


def test_parse_estoque_sem_quantidade_erro():
    with pytest.raises(ValueError, match="quantidade"):
        parse_estoque([{"SKU": "5338", "Preço": "9"}])


def test_importar_estoque_ajusta_saldo(cenario):
    linhas = parse_estoque([
        {"SKU": "5338", "Quantidade": "10", "Custo": ""},
        {"SKU": "8126", "Quantidade": "4", "Custo": "12,00"},
    ])
    r = importar_estoque(cenario, linhas)
    assert r.atualizados == 2
    assert r.saldos_criados == 2
    assert r.unidades_total == Decimal("14")
    # 5338: 10 * 6.50 (preço de compra) + 8126: 4 * 12.00 (custo da planilha)
    assert r.valor_total == Decimal("113.00")
    assert r.nao_encontrados == []
    assert svc.valor_total_estoque(cenario) == Decimal("113.00")


def test_importar_estoque_idempotente(cenario):
    linhas = parse_estoque([{"SKU": "5338", "Quantidade": "10"}])
    importar_estoque(cenario, linhas)
    importar_estoque(cenario, linhas)  # reimportar não duplica
    saldo = cenario.query(EstoqueSaldo).one()
    assert Decimal(str(saldo.qtd_disponivel)) == Decimal("10")


def test_importar_estoque_sku_nao_encontrado(cenario):
    linhas = parse_estoque([{"SKU": "9999", "Quantidade": "5"}])
    r = importar_estoque(cenario, linhas)
    assert r.atualizados == 0
    assert r.nao_encontrados == ["9999"]


def test_endpoint_importar_estoque(client, cenario):
    conteudo = _planilha([
        {"SKU": "5338", "Quantidade": 10},
        {"SKU": "8126", "Quantidade": 4},
    ])
    resp = client.post(
        "/api/estoque/importar",
        files={"arquivo": ("estoque.xlsx", conteudo,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["atualizados"] == 2
    assert body["local"] == "Galpão Central"
    assert body["unidades_total"] == "14.000"
