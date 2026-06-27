"""Validadores de documentos (CNPJ) e helpers de normalização."""
from __future__ import annotations

import re

_NAO_DIGITO = re.compile(r"\D")


def normalizar_cnpj(cnpj: str) -> str:
    """Remove tudo que não for dígito, mantendo apenas os 14 números."""
    return _NAO_DIGITO.sub("", cnpj or "")


def _digito_verificador(numeros: str, pesos: list[int]) -> int:
    soma = sum(int(d) * p for d, p in zip(numeros, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def validar_cnpj(cnpj: str) -> bool:
    """Valida um CNPJ pelos dois dígitos verificadores.

    Aceita o CNPJ com ou sem máscara. Rejeita comprimento != 14 e sequências
    de dígitos repetidos (ex.: ``00000000000000``).
    """
    numeros = normalizar_cnpj(cnpj)
    if len(numeros) != 14:
        return False
    if numeros == numeros[0] * 14:
        return False

    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    dv1 = _digito_verificador(numeros[:12], pesos_1)
    if dv1 != int(numeros[12]):
        return False

    dv2 = _digito_verificador(numeros[:13], pesos_2)
    return dv2 == int(numeros[13])


def formatar_cnpj(cnpj: str) -> str:
    """Formata como ``00.000.000/0000-00`` (assume CNPJ já normalizado/válido)."""
    n = normalizar_cnpj(cnpj)
    if len(n) != 14:
        return cnpj
    return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"
