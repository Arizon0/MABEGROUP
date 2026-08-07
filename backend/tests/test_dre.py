"""Testes do módulo DRE: extração de SKU, catálogo e cálculo da DRE."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.dre import GRUPO_GERAL, GRUPO_OPERACIONAL_ML
from app.models.produto import Produto
from app.models.venda import Venda
from app.parsers.common import CANAL_ML, CANAL_SHOPEE, STATUS_CANCELADO, STATUS_VALIDO
from app.services.catalogo import LinhaCatalogo, extrair_sku, importar_catalogo
from app.services.dre import calcular_dre, upsert_despesa
from app.seed.catalogo_seed import CATALOGO, seed_catalogo


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# extrair_sku — todos os exemplos oficiais do prompt                            #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "nome,esperado",
    [
        ("Retentor 5699", "5699"),
        ("Retentor 2373", "2373"),
        ("Aneis 9200STD", "9200STD"),
        ("Anel SDA7092", "7092"),
        ("Anel SDA6631 050", "6631050"),
        ("Jogo de Anel 7224-STD", "7224STD"),
        ("Jogo de Anel 7224 050", "7224050"),
        ("Bronzina De Biela SBB 1035-J 0,25", "1035J025"),
        ("Anel 8126 STD", "8126STD"),
        ("Aneis 8126050", "8126050"),
        ("Vedadores 9203", "9203"),
    ],
)
def test_extrair_sku_exemplos_oficiais(nome, esperado):
    assert extrair_sku(nome) == esperado


def test_extrair_sku_vazio():
    assert extrair_sku("") == ""
    assert extrair_sku("   ") == ""


# --------------------------------------------------------------------------- #
# Importação de catálogo                                                        #
# --------------------------------------------------------------------------- #
def test_importar_catalogo_upsert(db):
    linhas = [
        LinhaCatalogo("Retentor 5699", Decimal("95.00"), extrair_sku("Retentor 5699")),
        LinhaCatalogo("Anel SDA7092", Decimal("75.00"), extrair_sku("Anel SDA7092")),
    ]
    r1 = importar_catalogo(db, linhas)
    db.commit()
    assert r1.criados == 2
    assert r1.atualizados == 0

    prod = db.query(Produto).filter_by(sku_base="5699").one()
    assert prod.preco_compra == Decimal("95.00")
    assert prod.categoria == "Retentores"

    # Reimportar com custo diferente -> atualiza, não duplica.
    linhas2 = [LinhaCatalogo("Retentor 5699", Decimal("99.00"), "5699")]
    r2 = importar_catalogo(db, linhas2)
    db.commit()
    assert r2.criados == 0
    assert r2.atualizados == 1
    db.refresh(prod)
    assert prod.preco_compra == Decimal("99.00")


def test_seed_catalogo_cria_35_produtos(db):
    seed_catalogo(db)
    total = db.query(Produto).count()
    assert total == len(CATALOGO) == 35
    # SKU derivado corretamente para um caso com prefixo de letras.
    assert db.query(Produto).filter_by(sku_base="1035J025").count() == 1


# --------------------------------------------------------------------------- #
# Cálculo da DRE                                                                #
# --------------------------------------------------------------------------- #
def _venda(canal, sku, qtd, preco, custo, *, ano=2026, mes=1, status=STATUS_VALIDO):
    q = Decimal(str(qtd))
    p = Decimal(str(preco))
    c = Decimal(str(custo))
    return Venda(
        canal=canal,
        id_pedido_canal=f"{canal}-{sku}-{qtd}-{preco}",
        data_venda=datetime(ano, mes, 15),
        status_erp=status,
        sku_canal=sku,
        sku_base=sku,
        qtd=q,
        preco_unitario=p,
        custo_unitario=c,
        cmv=(c * q if status == STATUS_VALIDO else Decimal("0")),
        receita_bruta=(p * q if status == STATUS_VALIDO else Decimal("0")),
        liquido_recebido=p * q,
    )


def test_calcular_dre_receita_cmv_lucro_margens(db):
    # ML: 10 un x 100, custo 60 -> receita 1000, cmv 600
    db.add(_venda(CANAL_ML, "5699", 10, 100, 60))
    # Shopee: 5 un x 50, custo 20 -> receita 250, cmv 100
    db.add(_venda(CANAL_SHOPEE, "2373", 5, 50, 20))
    # Cancelada: não entra em receita nem CMV
    db.add(_venda(CANAL_ML, "5338", 3, 80, 40, status=STATUS_CANCELADO))
    db.commit()

    dre = calcular_dre(db, 2026, 1, "todos")

    assert dre["receitas"]["mercado_livre"] == "1000.00"
    assert dre["receitas"]["shopee"] == "250.00"
    assert dre["receitas"]["receita_bruta"] == "1250.00"
    assert dre["receitas"]["receita_liquida"] == "1250.00"
    assert dre["cmv"] == "700.00"
    assert dre["lucro_bruto"] == "550.00"
    # Sem despesas ainda: lucro operacional == lucro bruto.
    assert dre["lucro_operacional"] == "550.00"
    assert dre["lucro_liquido"] == "550.00"
    # Margem bruta = 550/1250 = 44%
    assert dre["margens"]["bruta"] == "44.00"


def test_dre_deducoes_e_despesas(db):
    db.add(_venda(CANAL_ML, "5699", 10, 100, 60))  # receita 1000, cmv 600
    db.commit()

    upsert_despesa(db, 2026, 1, "deducoes", "Cancelamentos", Decimal("100"))
    upsert_despesa(db, 2026, 1, GRUPO_OPERACIONAL_ML, "Comissão", Decimal("120"))
    upsert_despesa(db, 2026, 1, GRUPO_GERAL, "Salários", Decimal("80"))
    db.commit()

    dre = calcular_dre(db, 2026, 1, "todos")
    assert dre["receitas"]["receita_liquida"] == "900.00"   # 1000 - 100
    assert dre["lucro_bruto"] == "300.00"                    # 900 - 600
    assert dre["despesas_operacionais"]["total"] == "120.00"
    assert dre["lucro_operacional"] == "180.00"              # 300 - 120
    assert dre["despesas_gerais"]["total"] == "80.00"
    assert dre["lucro_liquido"] == "100.00"                  # 180 - 80


def test_dre_filtro_marketplace(db):
    db.add(_venda(CANAL_ML, "5699", 10, 100, 60))   # receita 1000
    db.add(_venda(CANAL_SHOPEE, "2373", 5, 50, 20)) # receita 250
    db.commit()

    dre_ml = calcular_dre(db, 2026, 1, CANAL_ML)
    assert dre_ml["receitas"]["receita_bruta"] == "1000.00"
    assert dre_ml["receitas"]["shopee"] == "0.00"

    dre_sh = calcular_dre(db, 2026, 1, CANAL_SHOPEE)
    assert dre_sh["receitas"]["receita_bruta"] == "250.00"


# --------------------------------------------------------------------------- #
# Endpoints                                                                     #
# --------------------------------------------------------------------------- #
def test_endpoint_dre_e_despesas(client, db):
    db.add(_venda(CANAL_ML, "5699", 4, 100, 60))
    db.commit()

    resp = client.put(
        "/api/dre/despesas",
        json={"ano": 2026, "mes": 1, "grupo": GRUPO_OPERACIONAL_ML,
              "categoria": "Comissão", "valor": "50"},
    )
    assert resp.status_code == 200

    dre = client.get("/api/dre?ano=2026&mes=1&marketplace=todos").json()
    assert dre["receitas"]["receita_bruta"] == "400.00"
    assert dre["cmv"] == "240.00"
    assert dre["despesas_operacionais"]["total"] == "50.00"

    export = client.get("/api/dre/export?ano=2026&mes=1&formato=excel")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith(
        "application/vnd.openxmlformats"
    )


def test_endpoint_importar_vendas_simples(client, db, tmp_path):
    import pandas as pd

    seed_catalogo(db)
    df = pd.DataFrame(
        [
            {"SKU": "5699", "Preço de Venda": "100", "Quantidade Vendida": "2",
             "Marketplace": "Mercado Livre", "Data": "2026-01-10"},
            {"SKU": "9999", "Preço de Venda": "10", "Quantidade Vendida": "1",
             "Marketplace": "Shopee", "Data": "2026-01-11"},
        ]
    )
    caminho = tmp_path / "vendas.xlsx"
    df.to_excel(caminho, index=False)

    with open(caminho, "rb") as fh:
        resp = client.post("/api/importar/vendas", files={"arquivo": ("vendas.xlsx", fh, "x")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["vendas_inseridas"] == 2
    assert "9999" in body["skus_nao_cadastrados"]

    # CMV congelado do 5699 (custo 95) * 2 = 190
    dre = client.get("/api/dre?ano=2026&mes=1&marketplace=todos").json()
    assert dre["cmv"] == "190.00"
