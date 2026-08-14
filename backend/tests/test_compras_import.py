"""Testes da importação de compras (entrada de estoque) e exclusão de saldo."""
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
from app.services.compras_import import importar_compras, parse_compras
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


# --------------------------------------------------------------------------- #
# Importação de compras                                                         #
# --------------------------------------------------------------------------- #


def test_parse_compras_detecta_colunas():
    linhas = parse_compras([
        {"SKU": "5338", "Quantidade": "10", "Valor pago": "6,00", "Frete": "20,00"},
    ])
    assert len(linhas) == 1
    assert linhas[0].qtd == Decimal("10")
    assert linhas[0].valor == Decimal("6.00")
    assert linhas[0].frete == Decimal("20.00")
    assert linhas[0].valor_eh_total is False


def test_importar_compras_landed_cost(cenario):
    # 10 un a R$6 + frete R$20 -> custo landed 6 + 20/10 = 8,00
    linhas = parse_compras([
        {"SKU": "5338", "Quantidade": "10", "Valor pago": "6,00", "Frete": "20,00"},
    ])
    r = importar_compras(cenario, linhas)
    assert r.entradas == 1
    assert r.unidades_total == Decimal("10")
    assert r.total_pago == Decimal("60.00")
    assert r.total_frete == Decimal("20.00")
    assert r.custo_total == Decimal("80.00")

    saldo = cenario.query(EstoqueSaldo).one()
    assert Decimal(str(saldo.qtd_disponivel)) == Decimal("10")
    assert Decimal(str(saldo.custo_medio)) == Decimal("8.0000")
    # preço de compra do produto atualizado para o custo landed
    p = cenario.query(Produto).filter_by(sku_base="5338").one()
    assert Decimal(str(p.preco_compra)) == Decimal("8.00")


def test_importar_compras_soma_ao_estoque(cenario):
    """Compra soma (não substitui) e recalcula custo médio ponderado."""
    importar_compras(cenario, parse_compras([
        {"SKU": "5338", "Quantidade": "10", "Valor pago": "6,00"},
    ]))
    importar_compras(cenario, parse_compras([
        {"SKU": "5338", "Quantidade": "10", "Valor pago": "8,00"},
    ]))
    saldo = cenario.query(EstoqueSaldo).one()
    assert Decimal(str(saldo.qtd_disponivel)) == Decimal("20")  # somou
    assert Decimal(str(saldo.custo_medio)) == Decimal("7.0000")  # média (6+8)/2


def test_importar_compras_valor_total(cenario):
    """Quando a planilha traz o valor total, é dividido pela quantidade."""
    linhas = parse_compras([
        {"SKU": "8126", "Quantidade": "5", "Valor total": "50,00"},
    ])
    assert linhas[0].valor_eh_total is True
    r = importar_compras(cenario, linhas)
    saldo = cenario.query(EstoqueSaldo).one()
    assert Decimal(str(saldo.custo_medio)) == Decimal("10.0000")
    assert r.custo_total == Decimal("50.00")


def test_endpoint_importar_compras(client, cenario):
    conteudo = _planilha([
        {"SKU": "5338", "Quantidade": 10, "Valor pago": 6.0, "Frete": 20.0},
        {"SKU": "8126", "Quantidade": 5, "Valor pago": 10.0, "Frete": 0.0},
    ])
    resp = client.post(
        "/api/estoque/importar-compras",
        files={"arquivo": ("compras.xlsx", conteudo,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["entradas"] == 2
    assert body["custo_total"] == "130.00"  # 60+20 + 50
    assert body["local"] == "Galpão Central"


# --------------------------------------------------------------------------- #
# Exclusão de saldo                                                             #
# --------------------------------------------------------------------------- #


def test_excluir_saldo(cenario):
    importar_estoque(cenario, parse_estoque([{"SKU": "5338", "Quantidade": "10"}]))
    saldo = cenario.query(EstoqueSaldo).one()
    svc.excluir_saldo(cenario, saldo.produto_id, saldo.local_id)
    assert cenario.query(EstoqueSaldo).count() == 0


def test_excluir_saldo_inexistente(cenario):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        svc.excluir_saldo(cenario, 999, 999)
    assert exc.value.status_code == 404


def test_endpoint_excluir_saldo(client, cenario):
    importar_estoque(cenario, parse_estoque([{"SKU": "5338", "Quantidade": "10"}]))
    saldo = cenario.query(EstoqueSaldo).one()
    resp = client.delete(f"/api/estoque/saldos/{saldo.produto_id}/{saldo.local_id}")
    assert resp.status_code == 200
    assert resp.json()["removido"] is True
    assert cenario.query(EstoqueSaldo).count() == 0
