"""Testes da importação de estoque atual via planilha."""
from __future__ import annotations

import io
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.estoque import (
    LOCAL_FULFILLMENT,
    LOCAL_GALPAO,
    EstoqueSaldo,
    Local,
)
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
    db.add(Local(nome="ML Fulfillment", tipo=LOCAL_FULFILLMENT))
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


def test_parse_estoque_formato_largo_dois_locais():
    """Colunas Galpão e ML Full geram uma entrada por local (célula vazia pula)."""
    linhas = parse_estoque([
        {"SKU": "5338", "Galpão": "10", "ML Full": "40"},
        {"SKU": "8126", "Galpão": "5", "ML Full": ""},  # sem full -> só galpão
    ])
    assert len(linhas) == 3
    assert (linhas[0].local_tipo, linhas[0].qtd) == (LOCAL_GALPAO, Decimal("10"))
    assert (linhas[1].local_tipo, linhas[1].qtd) == (LOCAL_FULFILLMENT, Decimal("40"))
    assert (linhas[2].local_tipo, linhas[2].qtd) == (LOCAL_GALPAO, Decimal("5"))


def test_importar_estoque_dois_locais(cenario):
    linhas = parse_estoque([
        {"SKU": "5338", "Galpão": "10", "ML Full": "40"},
        {"SKU": "8126", "Galpão": "5", "ML Full": "3"},
    ])
    r = importar_estoque(cenario, linhas)
    assert r.atualizados == 4
    assert set(r.locais) == {"Galpão Central", "ML Fulfillment"}
    # 5338: (10+40)*6.50=325 ; 8126: (5+3)*10=80  -> 405
    assert svc.valor_total_estoque(cenario) == Decimal("405.00")
    saldos = {
        (s.produto_id, s.local_id): Decimal(str(s.qtd_disponivel))
        for s in cenario.query(EstoqueSaldo).all()
    }
    assert len(saldos) == 4  # 2 SKUs × 2 locais


def test_parse_estoque_coluna_local(cenario):
    """Formato longo: coluna Local define o destino de cada linha."""
    linhas = parse_estoque([
        {"SKU": "5338", "Local": "Galpão", "Quantidade": "10"},
        {"SKU": "5338", "Local": "ML Full", "Quantidade": "40"},
    ])
    assert linhas[0].local_tipo == LOCAL_GALPAO
    assert linhas[1].local_tipo == LOCAL_FULFILLMENT
    r = importar_estoque(cenario, linhas)
    assert r.atualizados == 2
    assert set(r.locais) == {"Galpão Central", "ML Fulfillment"}


def test_importar_estoque_substitui_local(cenario):
    """A planilha vira a verdade do local: SKU ausente é zerado; outro local intacto."""
    # Estoque inicial: galpão tem 5338 e 8126; Full tem 5338.
    importar_estoque(cenario, parse_estoque([
        {"SKU": "5338", "Galpão": "10", "ML Full": "40"},
        {"SKU": "8126", "Galpão": "5", "ML Full": ""},
    ]))
    saldos = {
        (s.produto_id, s.local_id): Decimal(str(s.qtd_disponivel))
        for s in cenario.query(EstoqueSaldo).all()
    }
    assert len(saldos) == 3  # galpão:5338,8126 + full:5338

    # Reimporta SÓ o galpão, agora sem o 8126: ele deve ser zerado no galpão.
    r = importar_estoque(cenario, parse_estoque([
        {"SKU": "5338", "Galpão": "7"},
    ]))
    assert r.zerados == 1

    p5338 = cenario.query(Produto).filter_by(sku_base="5338").one()
    p8126 = cenario.query(Produto).filter_by(sku_base="8126").one()
    galpao = cenario.query(Local).filter_by(tipo=LOCAL_GALPAO).one()
    full = cenario.query(Local).filter_by(tipo=LOCAL_FULFILLMENT).one()

    def saldo(prod_id, local_id):
        s = cenario.query(EstoqueSaldo).filter_by(produto_id=prod_id, local_id=local_id).one()
        return Decimal(str(s.qtd_disponivel))

    assert saldo(p5338.id, galpao.id) == Decimal("7")   # atualizado
    assert saldo(p8126.id, galpao.id) == Decimal("0")   # zerado (ausente na planilha)
    assert saldo(p5338.id, full.id) == Decimal("40")    # Full intacto (não veio na planilha)


def test_endpoint_importar_estoque(client, cenario):
    conteudo = _planilha([
        {"SKU": "5338", "Galpão": 10, "ML Full": 40},
        {"SKU": "8126", "Galpão": 4, "ML Full": 0},
    ])
    resp = client.post(
        "/api/estoque/importar",
        files={"arquivo": ("estoque.xlsx", conteudo,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["atualizados"] == 4
    assert set(body["locais"]) == {"Galpão Central", "ML Fulfillment"}
    assert body["unidades_total"] == "54.000"
    assert {p["local"] for p in body["por_local"]} == {"Galpão Central", "ML Fulfillment"}
