"""Testes do parser da Shopee."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.parsers.common import STATUS_CANCELADO, STATUS_VALIDO
from app.parsers.shopee import calcular_liquido_shopee, parse_shopee
from app.services.totais import calcular_totais
from tests.factories import build_shopee_xlsx


@pytest.fixture()
def shopee_file(tmp_path):
    return build_shopee_xlsx(tmp_path / "shopee.xlsx")


def test_totais_batem_com_esperado(shopee_file):
    path, esperado = shopee_file
    dtos = parse_shopee(path)
    assert len(dtos) == esperado["dtos"]

    t = calcular_totais(dtos)
    assert t.linhas == esperado["linhas"]
    assert t.unidades == esperado["unidades"]
    assert t.receita_bruta == esperado["receita_bruta"]
    assert t.tarifas_plataforma == esperado["tarifas_plataforma"]
    assert t.frete_liquido == esperado["frete_liquido"]
    assert t.liquido_recebido == esperado["liquido_recebido"]


def test_cancelado_e_nao_pago_zeram(shopee_file):
    path, _ = shopee_file
    dtos = {d.id_pedido_canal: d for d in parse_shopee(path)}

    s2 = dtos["S2"]  # Cancelado
    assert s2.status_erp == STATUS_CANCELADO
    assert s2.qtd == Decimal("0")
    assert s2.receita_bruta == Decimal("0")
    assert s2.liquido_recebido == Decimal("0")
    assert s2.tarifas_plataforma == Decimal("0")

    s3 = dtos["S3"]  # Não pago
    assert s3.status_erp == STATUS_CANCELADO
    assert s3.liquido_recebido == Decimal("0")


def test_fallback_sku(shopee_file):
    path, _ = shopee_file
    dtos = {d.id_pedido_canal: d for d in parse_shopee(path)}
    # S2 tem "Número de referência SKU" vazio -> usa o principal
    assert dtos["S2"].sku_canal == "8126STA"
    # S4 idem
    assert dtos["S4"].sku_canal == "2178"
    # S1 usa o SKU normal
    assert dtos["S1"].sku_canal == "5338"


def test_liquido_valido(shopee_file):
    path, _ = shopee_file
    dtos = {d.id_pedido_canal: d for d in parse_shopee(path)}
    s1 = dtos["S1"]
    assert s1.status_erp == STATUS_VALIDO
    # 100 - 8 - 4 - 2 - 0 = 86
    assert s1.liquido_recebido == Decimal("86")
    assert s1.tarifas_plataforma == Decimal("-14")
    assert isinstance(s1.liquido_recebido, Decimal)


def test_calcular_liquido_shopee_dict():
    row_ok = {
        "Status do pedido": "Concluído",
        "Subtotal do produto": "100",
        "Taxa de comissão líquida": "8",
        "Taxa de serviço líquida": "4",
        "Taxa de transação": "2",
        "Taxa de Envio Reversa": "0",
    }
    assert calcular_liquido_shopee(row_ok) == Decimal("86")

    row_cancel = dict(row_ok, **{"Status do pedido": "Cancelado"})
    assert calcular_liquido_shopee(row_cancel) == Decimal("0")
