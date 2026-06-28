"""Testes dos helpers de conversão de valores."""
from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal

from app.parsers.common import is_empty, to_datetime, to_decimal, to_str


def test_to_decimal_formatos():
    assert to_decimal(None) == Decimal("0")
    assert to_decimal(float("nan")) == Decimal("0")
    assert to_decimal("") == Decimal("0")
    assert to_decimal("nan") == Decimal("0")
    assert to_decimal(10) == Decimal("10")
    assert to_decimal(-5.5) == Decimal("-5.5")
    assert to_decimal("1.234,56") == Decimal("1234.56")  # formato brasileiro
    assert to_decimal("1234,56") == Decimal("1234.56")
    assert to_decimal("R$ 1.234,56") == Decimal("1234.56")
    assert to_decimal("-7901.91") == Decimal("-7901.91")


def test_to_decimal_nao_usa_float_artefato():
    # Decimal('0.1') exato, sem ruído de ponto flutuante.
    assert to_decimal("0.1") == Decimal("0.1")


def test_to_str_normaliza():
    assert to_str(None) == ""
    assert to_str(float("nan")) == ""
    assert to_str("  5338  ") == "5338"
    assert to_str(1942.0) == "1942"  # float inteiro vira string limpa


def test_is_empty():
    assert is_empty(None)
    assert is_empty(float("nan"))
    assert is_empty("  ")
    assert is_empty("NaN")
    assert not is_empty("0")
    assert not is_empty(0)


def test_to_datetime():
    assert to_datetime("2026-05-10 10:30") == datetime(2026, 5, 10, 10, 30)
    assert to_datetime("10/05/2026 10:30") == datetime(2026, 5, 10, 10, 30)
    assert to_datetime("2026-05-10") == datetime(2026, 5, 10)
    assert to_datetime(None) is None
    assert to_datetime("texto inválido") is None
