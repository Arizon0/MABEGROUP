"""Testes de Dashboard e Relatórios (Prioridade 5)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.estoque import LOCAL_GALPAO, Local
from app.models.produto import Produto
from app.models.venda import Venda
from app.services import analytics
from app.services.estoque import registrar_entrada


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _venda(**kw) -> Venda:
    base = dict(
        canal="Mercado Livre", id_pedido_canal="X", status_erp="Válido",
        sku_base=None, qtd=Decimal("0"), receita_bruta=Decimal("0"),
        tarifas_plataforma=Decimal("0"), frete_liquido=Decimal("0"),
        descontos=Decimal("0"), cancelamentos=Decimal("0"),
        liquido_recebido=Decimal("0"), data_venda=datetime(2026, 6, 20),
    )
    base.update(kw)
    return Venda(**base)


@pytest.fixture()
def cenario(db):
    db.add_all([
        Produto(sku_base="5338", nome="Retentor", preco_compra=Decimal("5.00")),
        Produto(sku_base="8126", nome="Anel", preco_compra=Decimal("10.00")),
    ])
    db.add_all([
        _venda(canal="Mercado Livre", id_pedido_canal="V1", sku_base="5338",
               qtd=Decimal("2"), receita_bruta=Decimal("100"),
               tarifas_plataforma=Decimal("-15"), frete_liquido=Decimal("-5"),
               liquido_recebido=Decimal("80"), data_venda=datetime(2026, 6, 20)),
        _venda(canal="Shopee", id_pedido_canal="V2", sku_base="8126",
               qtd=Decimal("1"), receita_bruta=Decimal("50"),
               tarifas_plataforma=Decimal("-7"),
               liquido_recebido=Decimal("43"), data_venda=datetime(2026, 6, 21)),
        _venda(canal="Mercado Livre", id_pedido_canal="V3", sku_base="8126",
               qtd=Decimal("1"), receita_bruta=Decimal("30"),
               liquido_recebido=Decimal("25"), data_venda=datetime(2026, 5, 10)),
        # cancelada -> ignorada nos relatórios
        _venda(canal="Mercado Livre", id_pedido_canal="V4", sku_base="5338",
               status_erp="Cancelado", qtd=Decimal("9"), receita_bruta=Decimal("999"),
               liquido_recebido=Decimal("999"), data_venda=datetime(2026, 6, 1)),
    ])
    db.flush()
    return db


def test_dashboard(cenario):
    d = analytics.dashboard(cenario)
    assert d["faturamento_bruto"] == "180.00"
    assert d["liquido_total"] == "148.00"
    assert d["liquido_por_canal"]["Mercado Livre"] == "105.00"
    assert d["liquido_por_canal"]["Shopee"] == "43.00"
    assert d["custo_produtos_vendidos"] == "30.00"  # 2*5 + 2*10
    assert d["lucro_estimado"] == "118.00"
    assert set(d["projecoes"].keys()) == {"15", "30", "60", "90"}


def test_dre(cenario):
    dre = analytics.dre(cenario)
    assert dre["receita_bruta"] == "180.00"
    assert dre["tarifas_plataforma"] == "-22.00"
    assert dre["frete_liquido"] == "-5.00"
    assert dre["liquido_recebido"] == "148.00"
    assert dre["custo_produtos_vendidos"] == "30.00"
    assert dre["margem_bruta"] == "118.00"


def test_dre_filtro_canal(cenario):
    dre = analytics.dre(cenario, canal="Shopee")
    assert dre["receita_bruta"] == "50.00"
    assert dre["liquido_recebido"] == "43.00"


def test_ranking_receita(cenario):
    r = analytics.ranking_receita(cenario)
    assert r[0]["sku_base"] == "5338"  # 80 líquido
    assert r[0]["liquido"] == "80.00"
    assert r[1]["sku_base"] == "8126"  # 43 + 25 = 68
    assert r[1]["liquido"] == "68.00"


def test_giro_estoque(cenario, db):
    galpao = Local(nome="Galpão", tipo=LOCAL_GALPAO)
    db.add(galpao)
    db.flush()
    p5338 = db.query(Produto).filter(Produto.sku_base == "5338").one()
    registrar_entrada(db, produto_id=p5338.id, local_id=galpao.id, qtd=Decimal("4"),
                      custo_unitario=Decimal("5"))

    giro = {g["sku_base"]: g for g in analytics.giro_estoque(cenario)}
    # CMV 5338 = 2*5 = 10; estoque 4 -> giro 2.5
    assert giro["5338"]["custo_mercadorias_vendidas"] == "10.00"
    assert giro["5338"]["giro"] == "2.500"
    # 8126 sem estoque -> giro None
    assert giro["8126"]["giro"] is None


def test_fluxo_caixa(cenario):
    fluxo = analytics.fluxo_caixa(cenario)
    por_mes = {f["mes"]: f["liquido_recebido"] for f in fluxo}
    assert por_mes["2026-05"] == "25.00"
    assert por_mes["2026-06"] == "123.00"  # 80 + 43


# --------------------------------------------------------------------------- #
# Endpoints + export                                                            #
# --------------------------------------------------------------------------- #


def test_endpoint_dashboard(client, cenario):
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    assert resp.json()["liquido_total"] == "148.00"


def test_endpoint_relatorio_json(client, cenario):
    resp = client.get("/api/relatorios/dre")
    assert resp.status_code == 200
    assert resp.json()["margem_bruta"] == "118.00"


def test_relatorio_filtro_periodo(client, cenario):
    # Só maio -> apenas V3 (líquido 25)
    resp = client.get(
        "/api/relatorios/dre",
        params={"data_inicio": "2026-05-01", "data_fim": "2026-05-31"},
    )
    assert resp.json()["liquido_recebido"] == "25.00"


def test_export_excel(client, cenario):
    resp = client.get("/api/relatorios/ranking", params={"formato": "excel"})
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    assert resp.content[:2] == b"PK"  # zip/xlsx


def test_export_pdf(client, cenario):
    resp = client.get("/api/relatorios/dre", params={"formato": "pdf"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


def test_relatorio_tipo_invalido(client):
    assert client.get("/api/relatorios/inexistente").status_code == 404
