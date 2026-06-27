"""Teste de integração contra as PLANILHAS REAIS (mai–jun 2026).

Estes testes só rodam se os arquivos reais estiverem disponíveis. Aponte-os por
variável de ambiente ou coloque-os em ``backend/tests/data/``:

    ERP_ML_XLSX=/caminho/Vendas_BR_MercadoLibre_*.xlsx
    ERP_SHOPEE_XLSX=/caminho/Order_all_*.xlsx

Os números de validação vêm da seção "Dados Reais de Validação" do CLAUDE.md.
Se a soma não bater, o parsing tem bug.
"""
from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pytest

from app.parsers.mercadolivre import parse_ml
from app.parsers.shopee import parse_shopee
from app.services.totais import calcular_totais

DATA_DIR = Path(__file__).parent / "data"
CENT = Decimal("0.01")


def _achar(env: str, padrao: str) -> Path | None:
    caminho = os.getenv(env)
    if caminho and Path(caminho).exists():
        return Path(caminho)
    if DATA_DIR.exists():
        encontrados = sorted(DATA_DIR.glob(padrao))
        if encontrados:
            return encontrados[0]
    return None


ML_FILE = _achar("ERP_ML_XLSX", "Vendas_BR_MercadoLibre_*.xlsx")
SHOPEE_FILE = _achar("ERP_SHOPEE_XLSX", "Order_all_*.xlsx")

# Valores esperados (CLAUDE.md → Dados Reais de Validação).
ML_ESPERADO = {
    "linhas": 678,
    "unidades": Decimal("758"),
    "receita_bruta": Decimal("52026.43"),
    "tarifas_plataforma": Decimal("-7901.91"),
    "frete_liquido": Decimal("-9989.47"),
    "descontos": Decimal("664.15"),
    "cancelamentos": Decimal("-1894.76"),
    "liquido_recebido": Decimal("32904.44"),
}
SHOPEE_ESPERADO = {
    "linhas": 216,
    "unidades": Decimal("216"),
    "receita_bruta": Decimal("10385.88"),
    "tarifas_plataforma": Decimal("-3002.18"),
    "liquido_recebido": Decimal("7383.70"),
}


def _quase(a: Decimal, b: Decimal, tol: Decimal = CENT) -> bool:
    return abs(Decimal(a) - Decimal(b)) <= tol


@pytest.mark.skipif(ML_FILE is None, reason="planilha real do ML não disponível")
def test_ml_validacao_real():
    t = calcular_totais(parse_ml(ML_FILE))
    assert t.linhas == ML_ESPERADO["linhas"]
    assert _quase(t.unidades, ML_ESPERADO["unidades"])
    assert _quase(t.receita_bruta, ML_ESPERADO["receita_bruta"])
    assert _quase(t.tarifas_plataforma, ML_ESPERADO["tarifas_plataforma"])
    assert _quase(t.frete_liquido, ML_ESPERADO["frete_liquido"])
    assert _quase(t.descontos, ML_ESPERADO["descontos"])
    assert _quase(t.cancelamentos, ML_ESPERADO["cancelamentos"])
    assert _quase(t.liquido_recebido, ML_ESPERADO["liquido_recebido"])


@pytest.mark.skipif(SHOPEE_FILE is None, reason="planilha real da Shopee não disponível")
def test_shopee_validacao_real():
    t = calcular_totais(parse_shopee(SHOPEE_FILE))
    assert t.linhas == SHOPEE_ESPERADO["linhas"]
    assert _quase(t.unidades, SHOPEE_ESPERADO["unidades"])
    assert _quase(t.receita_bruta, SHOPEE_ESPERADO["receita_bruta"])
    assert _quase(t.tarifas_plataforma, SHOPEE_ESPERADO["tarifas_plataforma"])
    assert _quase(t.liquido_recebido, SHOPEE_ESPERADO["liquido_recebido"])


@pytest.mark.skipif(
    ML_FILE is None or SHOPEE_FILE is None,
    reason="planilhas reais não disponíveis",
)
def test_total_geral_real():
    t_ml = calcular_totais(parse_ml(ML_FILE))
    t_shopee = calcular_totais(parse_shopee(SHOPEE_FILE))
    liquido_total = t_ml.liquido_recebido + t_shopee.liquido_recebido
    assert _quase(liquido_total, Decimal("40288.14"))
