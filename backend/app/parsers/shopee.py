"""Parser do relatório de pedidos da Shopee.

Arquivo: ``Order_all_*.xlsx`` | Aba: ``orders`` | Cabeçalho na linha 1.

Pontos críticos (ver "Armadilhas de Parsing" no CLAUDE.md):
  - A Shopee NÃO entrega o líquido pronto: ele é calculado.
  - Pedidos cancelados/não pagos ainda vêm com qtd e subtotal preenchidos no
    arquivo -> precisam ser zerados ANTES de qualquer soma.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, Union

import pandas as pd

from .common import (
    CANAL_SHOPEE,
    STATUS_CANCELADO,
    STATUS_VALIDO,
    VendaDTO,
    to_datetime,
    to_decimal,
    to_str,
)

ZERO = Decimal("0")

# Nomes exatos das colunas no arquivo da Shopee.
COL_ID = "ID do pedido"
COL_DATA = "Data de criação do pedido"
COL_STATUS = "Status do pedido"
COL_SKU = "Número de referência SKU"
COL_SKU_FALLBACK = "Nº de referência do SKU principal"
COL_TITULO = "Nome do Produto"
COL_VARIACAO = "Nome da variação"
COL_PRECO = "Preço acordado"
COL_QTD = "Quantidade"
COL_SUBTOTAL = "Subtotal do produto"
COL_COMISSAO = "Taxa de comissão líquida"
COL_SERVICO = "Taxa de serviço líquida"
COL_TRANSACAO = "Taxa de transação"
COL_ENVIO_REVERSO = "Taxa de Envio Reversa"

STATUS_ZERAR = {"Cancelado", "Não pago"}


def calcular_liquido_shopee(row: Any) -> Decimal:
    """Líquido = Subtotal − comissão − serviço − transação − envio reverso.

    Pedidos cancelados/não pagos retornam 0.
    """
    if to_str(_get(row, COL_STATUS)) in STATUS_ZERAR:
        return ZERO
    return (
        to_decimal(_get(row, COL_SUBTOTAL))
        - to_decimal(_get(row, COL_COMISSAO))
        - to_decimal(_get(row, COL_SERVICO))
        - to_decimal(_get(row, COL_TRANSACAO))
        - to_decimal(_get(row, COL_ENVIO_REVERSO))
    )


def parse_shopee(path: Union[str, Path]) -> list[VendaDTO]:
    """Lê o arquivo da Shopee e retorna uma lista de ``VendaDTO``."""
    df = pd.read_excel(path, sheet_name=0, header=0, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]
    return [_build_dto(row) for _, row in df.iterrows()]


# --------------------------------------------------------------------------- #
# Internos                                                                      #
# --------------------------------------------------------------------------- #


def _get(row: Any, col: str):
    try:
        if col in row.index:
            return row[col]
    except AttributeError:
        if isinstance(row, dict):
            return row.get(col)
    return None


def _sku(row: Any) -> str:
    sku = to_str(_get(row, COL_SKU))
    if not sku:
        sku = to_str(_get(row, COL_SKU_FALLBACK))
    return sku


def _build_dto(row: Any) -> VendaDTO:
    status_canal = to_str(_get(row, COL_STATUS))
    cancelado = status_canal in STATUS_ZERAR

    if cancelado:
        qtd = ZERO
        receita = ZERO
        liquido = ZERO
    else:
        qtd = to_decimal(_get(row, COL_QTD))
        receita = to_decimal(_get(row, COL_SUBTOTAL))
        liquido = calcular_liquido_shopee(row)

    # Na Shopee não há frete líquido próprio nem descontos no schema unificado;
    # todas as tarifas (comissão, serviço, transação, envio reverso) entram em
    # tarifas_plataforma. tarifas = liquido − receita (negativo).
    tarifas = liquido - receita

    return VendaDTO(
        canal=CANAL_SHOPEE,
        id_pedido_canal=to_str(_get(row, COL_ID)),
        data_venda=to_datetime(_get(row, COL_DATA)),
        status_canal=status_canal,
        status_erp=STATUS_CANCELADO if cancelado else STATUS_VALIDO,
        sku_canal=_sku(row),
        id_anuncio=None,
        titulo=to_str(_get(row, COL_TITULO)),
        tipo_anuncio="Shopee",
        canal_logistico="Shopee",
        variacao=to_str(_get(row, COL_VARIACAO)) or None,
        qtd=qtd,
        preco_unitario=to_decimal(_get(row, COL_PRECO)),
        receita_bruta=receita,
        tarifas_plataforma=tarifas,
        frete_liquido=ZERO,
        descontos=ZERO,
        cancelamentos=ZERO,
        liquido_recebido=liquido,
        is_pacote_multi=False,
    )
