"""Testes do validador de CNPJ."""
from __future__ import annotations

from app.services.validators import (
    formatar_cnpj,
    normalizar_cnpj,
    validar_cnpj,
)


def test_cnpj_valido_com_e_sem_mascara():
    assert validar_cnpj("11.222.333/0001-81") is True
    assert validar_cnpj("11222333000181") is True
    assert validar_cnpj("11.222.333/0002-62") is True


def test_cnpj_invalido_digito_verificador():
    assert validar_cnpj("11.222.333/0001-82") is False
    assert validar_cnpj("11222333000180") is False


def test_cnpj_invalido_tamanho():
    assert validar_cnpj("123") is False
    assert validar_cnpj("") is False
    assert validar_cnpj("112223330001811") is False  # 15 dígitos


def test_cnpj_repetido_e_invalido():
    assert validar_cnpj("00000000000000") is False
    assert validar_cnpj("11111111111111") is False


def test_normalizar_e_formatar():
    assert normalizar_cnpj("11.222.333/0001-81") == "11222333000181"
    assert formatar_cnpj("11222333000181") == "11.222.333/0001-81"
