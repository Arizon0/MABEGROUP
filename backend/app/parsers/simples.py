"""Parser da planilha de vendas simples (formato genérico da DRE).

Formato esperado (colunas, nomes flexíveis / case-insensitive):

    SKU | Preço de Venda | Quantidade Vendida | Marketplace | Data

Diferente dos relatórios oficiais do ML/Shopee, aqui a receita bruta é
calculada (``qtd × preço``) e o SKU já é o ``sku_base`` do cadastro. Como não
há número de pedido, geramos uma chave determinística por linha para permitir
reimportar o mesmo arquivo sem duplicar (regra: importar de novo não duplica).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from app.parsers.common import (
    CANAL_ML,
    CANAL_SHOPEE,
    STATUS_VALIDO,
    VendaDTO,
    ler_linhas_csv,
    ler_linhas_xlsx,
    to_datetime,
    to_decimal,
    to_str,
)

_COLS_SKU = ("sku", "código", "codigo", "sku base")
_COLS_PRECO = ("preço de venda", "preco de venda", "preço", "preco", "valor de venda", "preço unitário")
_COLS_QTD = ("quantidade vendida", "quantidade", "qtd", "unidades", "qtde")
_COLS_MKT = ("marketplace", "canal", "plataforma")
_COLS_DATA = ("data", "data da venda", "data de venda", "data do pedido")


def _achar(colunas: list[str], candidatos: tuple[str, ...]) -> str | None:
    norm = {str(c).strip().lower(): c for c in colunas}
    for cand in candidatos:
        if cand in norm:
            return norm[cand]
    for chave, original in norm.items():
        if any(cand in chave for cand in candidatos):
            return original
    return None


def _normalizar_canal(valor: str) -> str:
    v = (valor or "").strip().lower()
    if "shop" in v:
        return CANAL_SHOPEE
    if "livre" in v or v in {"ml", "mercadolivre", "meli", "mercado livre"}:
        return CANAL_ML
    if "mercado" in v:
        return CANAL_ML
    return valor.strip() or CANAL_ML


def _chave_linha(canal: str, sku: str, data: str, preco: str, qtd: str, indice: int) -> str:
    bruto = f"{canal}|{sku}|{data}|{preco}|{qtd}|{indice}"
    return "S" + hashlib.sha1(bruto.encode("utf-8")).hexdigest()[:16]


def parse_simples(path: str | Path) -> list[VendaDTO]:
    """Lê a planilha simples (.xlsx/.csv) e devolve ``VendaDTO`` por linha.

    A receita e o CMV finais são resolvidos na camada de importação, que busca
    o custo do produto pelo ``sku_base``.
    """
    caminho = Path(path)
    if caminho.suffix.lower() == ".csv":
        linhas = ler_linhas_csv(caminho)
    else:
        linhas = ler_linhas_xlsx(caminho, header_row=0)

    if not linhas:
        return []

    colunas = list(linhas[0].keys())
    col_sku = _achar(colunas, _COLS_SKU)
    col_preco = _achar(colunas, _COLS_PRECO)
    col_qtd = _achar(colunas, _COLS_QTD)
    col_mkt = _achar(colunas, _COLS_MKT)
    col_data = _achar(colunas, _COLS_DATA)

    faltando = [
        nome
        for nome, col in (("SKU", col_sku), ("Preço de Venda", col_preco),
                          ("Quantidade", col_qtd), ("Marketplace", col_mkt))
        if col is None
    ]
    if faltando:
        raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(faltando)}")

    vendas: list[VendaDTO] = []
    for indice, row in enumerate(linhas):
        sku = to_str(row.get(col_sku))
        if not sku:
            continue
        preco = to_decimal(row.get(col_preco))
        qtd = to_decimal(row.get(col_qtd))
        canal = _normalizar_canal(to_str(row.get(col_mkt)))
        data_raw = to_str(row.get(col_data)) if col_data else ""
        data = to_datetime(row.get(col_data)) if col_data else None

        receita = preco * qtd
        pedido = _chave_linha(canal, sku, data_raw, str(preco), str(qtd), indice)

        vendas.append(
            VendaDTO(
                canal=canal,
                id_pedido_canal=pedido,
                data_venda=data,
                status_canal="",
                status_erp=STATUS_VALIDO,
                sku_canal=sku,
                sku_base=None,
                titulo="",
                canal_logistico=canal,
                qtd=qtd,
                preco_unitario=preco,
                receita_bruta=receita,
                liquido_recebido=receita,
            )
        )
    return vendas
