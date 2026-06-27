"""Testes de integração do serviço de importação + resolução de SKU."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select

from app.models.sku_map import SkuPendencia
from app.models.venda import Venda
from app.parsers.mercadolivre import parse_ml
from app.seed import seed_sku_map
from app.services.importacao import importar_vendas
from app.parsers.common import CANAL_ML
from tests.factories import build_ml_xlsx


def test_seed_cria_produtos_e_mapeamentos(db):
    res = seed_sku_map(db)
    assert res["produtos_criados"] == 20  # 20 sku_base no de-para
    assert res["mapeamentos_criados"] > 20  # vários sku_canal por base
    # idempotente
    res2 = seed_sku_map(db)
    assert res2["produtos_criados"] == 0
    assert res2["mapeamentos_criados"] == 0


def test_importacao_resolve_skus_e_registra_pendencias(db, tmp_path):
    seed_sku_map(db)  # 5338, 5245, 5699, 8126 estão mapeados; "" e fictícios não
    path, _ = build_ml_xlsx(tmp_path / "ml.xlsx")
    vendas = parse_ml(path)

    resultado = importar_vendas(db, vendas, CANAL_ML)
    db.commit()

    # SKUs do fixture (5338, 8126, 5245, 5699) são mapeados.
    assert resultado.skus_resolvidos >= 4
    # Nenhuma pendência: todos os SKUs presentes existem no seed.
    assert resultado.skus_pendentes == 0

    # vendas persistidas == DTOs (nenhum duplicado na 1ª importação)
    total_vendas = db.execute(select(func.count()).select_from(Venda)).scalar_one()
    assert total_vendas == resultado.vendas_inseridas == len(vendas)

    # sku_base preenchido nas linhas com sku_canal conhecido
    v5338 = db.execute(
        select(Venda).where(Venda.sku_canal == "5338")
    ).scalars().first()
    assert v5338.sku_base == "5338"


def test_pendencia_quando_sku_desconhecido(db, tmp_path):
    # Sem seed: nenhum SKU é conhecido -> pendências para cada sku_canal não vazio.
    path, _ = build_ml_xlsx(tmp_path / "ml.xlsx")
    vendas = parse_ml(path)

    resultado = importar_vendas(db, vendas, CANAL_ML)
    db.commit()

    assert resultado.skus_resolvidos == 0
    # sku_canal distintos não vazios no fixture: 5338, 8126, 5245, 5699
    assert resultado.skus_pendentes == 4
    pend = db.execute(select(SkuPendencia)).scalars().all()
    assert {p.sku_canal for p in pend} == {"5338", "8126", "5245", "5699"}
    # 5245 aparece em 2 linhas (componente do pacote + V4) -> ocorrências>=2
    p5245 = next(p for p in pend if p.sku_canal == "5245")
    assert p5245.ocorrencias >= 2


def test_importacao_duplicada_e_ignorada(db, tmp_path):
    seed_sku_map(db)
    path, _ = build_ml_xlsx(tmp_path / "ml.xlsx")
    vendas = parse_ml(path)

    r1 = importar_vendas(db, vendas, CANAL_ML)
    db.commit()
    inseridas_1 = r1.vendas_inseridas

    # Reimportar o mesmo arquivo: todos os pedidos já existem.
    r2 = importar_vendas(db, parse_ml(path), CANAL_ML)
    db.commit()
    assert r2.vendas_inseridas == 0
    assert r2.pedidos_duplicados == 5  # V1..V5 (V3 conta 1 pedido)

    total = db.execute(select(func.count()).select_from(Venda)).scalar_one()
    assert total == inseridas_1  # nada duplicado no banco


def test_totais_da_importacao(db, tmp_path):
    path, esperado = build_ml_xlsx(tmp_path / "ml.xlsx")
    resultado = importar_vendas(db, parse_ml(path), CANAL_ML)
    assert resultado.totais.liquido_recebido == esperado["liquido_recebido"]
    assert resultado.totais.unidades == esperado["unidades"]
