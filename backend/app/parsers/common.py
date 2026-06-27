"""Schema unificado interno e helpers de parsing compartilhados entre canais.

Toda operação financeira usa ``Decimal`` (nunca ``float``), conforme as regras
do projeto. Os helpers aqui concentram a conversão de valores "sujos" vindos das
planilhas (NaN, strings em formato brasileiro, células vazias) para tipos limpos.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

CANAL_ML = "Mercado Livre"
CANAL_SHOPEE = "Shopee"

STATUS_VALIDO = "Válido"
STATUS_CANCELADO = "Cancelado"
STATUS_DEVOLUCAO = "Devolução"


@dataclass
class VendaDTO:
    """Linha de venda normalizada, igual para Mercado Livre e Shopee."""

    canal: str                       # 'Mercado Livre' | 'Shopee'
    id_pedido_canal: str
    data_venda: Optional[datetime]
    status_canal: str                # status original do canal
    status_erp: str                  # 'Válido' | 'Cancelado' | 'Devolução'
    sku_canal: str                   # código como veio no relatório
    sku_base: Optional[str] = None   # preenchido após lookup na tabela sku_map
    id_anuncio: Optional[str] = None
    titulo: str = ""
    tipo_anuncio: Optional[str] = None   # 'Premium', 'Clássico', 'Shopee'
    canal_logistico: str = ""        # 'ML Full', 'ML Flex', 'Shopee' etc.
    variacao: Optional[str] = None
    qtd: Decimal = Decimal("0")
    preco_unitario: Decimal = Decimal("0")
    receita_bruta: Decimal = Decimal("0")
    tarifas_plataforma: Decimal = Decimal("0")  # negativo
    frete_liquido: Decimal = Decimal("0")        # pode ser negativo
    descontos: Decimal = Decimal("0")            # positivo
    cancelamentos: Decimal = Decimal("0")        # negativo
    liquido_recebido: Decimal = Decimal("0")     # valor final recebido
    is_pacote_multi: bool = False


# --------------------------------------------------------------------------- #
# Conversão de valores                                                          #
# --------------------------------------------------------------------------- #

_EMPTY_TOKENS = {"", "nan", "none", "nat", "null", "-"}


def is_empty(value: Any) -> bool:
    """True para None, NaN, NaT ou string vazia/placeholder."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    text = str(value).strip().lower()
    return text in _EMPTY_TOKENS


def to_str(value: Any) -> str:
    """Normaliza uma célula para string limpa ('' quando vazia)."""
    if is_empty(value):
        return ""
    text = str(value).strip()
    # openpyxl/pandas às vezes trazem floats inteiros como '1942.0'
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def to_decimal(value: Any) -> Decimal:
    """Converte valor de planilha para ``Decimal``.

    Trata NaN/None/vazio como 0 e aceita formato brasileiro ('1.234,56').
    """
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return Decimal("0")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return Decimal("0")
        return Decimal(str(value))

    text = str(value).strip()
    if text.lower() in _EMPTY_TOKENS:
        return Decimal("0")

    text = (
        text.replace("R$", "")
        .replace("\xa0", "")
        .replace(" ", "")
    )
    # Formato brasileiro: 1.234,56 -> 1234.56 ; 1234,56 -> 1234.56
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%d-%m-%Y",
)


def to_datetime(value: Any) -> Optional[datetime]:
    """Converte célula de data para ``datetime`` (None quando não parseável)."""
    if is_empty(value):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("T", " ")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
