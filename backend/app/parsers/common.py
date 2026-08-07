"""Schema unificado interno e helpers de parsing compartilhados entre canais.

Toda operação financeira usa ``Decimal`` (nunca ``float``), conforme as regras
do projeto. Os helpers aqui concentram a conversão de valores "sujos" vindos das
planilhas (NaN, strings em formato brasileiro, células vazias) para tipos limpos.
"""
from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

import openpyxl

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


# --------------------------------------------------------------------------- #
# Leitura de planilhas (openpyxl / csv) — substitui o pandas no runtime         #
# --------------------------------------------------------------------------- #


def ler_linhas_xlsx(source: Any, *, header_row: int = 0, sheet: int = 0) -> list[dict]:
    """Lê uma planilha (.xlsx) e devolve as linhas como ``list[dict]``.

    - ``source`` pode ser um caminho ou um objeto file-like (ex.: ``BytesIO``).
    - ``header_row`` é o índice 0-based da linha de cabeçalho (linhas acima são
      metadados e ignoradas), equivalente ao ``header=`` do ``pd.read_excel``.
    - Colunas com o **mesmo nome** colapsam para a **primeira** ocorrência —
      replica o comportamento de que ``row["Unidades"]`` usa a 1ª coluna
      ``Unidades`` do relatório do Mercado Livre (armadilha nº 3 do CLAUDE.md).
    - Linhas totalmente vazias são descartadas (equivalente ao trim do pandas).
    """
    wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[sheet]
        linhas = list(ws.iter_rows(min_row=header_row + 1, values_only=True))
    finally:
        wb.close()

    if not linhas:
        return []

    cabecalho = [to_str(c) for c in linhas[0]]
    registros: list[dict] = []
    for bruta in linhas[1:]:
        if bruta is None or all(v is None for v in bruta):
            continue
        registro: dict = {}
        for nome, valor in zip(cabecalho, bruta):
            if not nome or nome in registro:  # ignora sem nome; 1ª duplicata vence
                continue
            registro[nome] = valor
        registros.append(registro)
    return registros


def ler_linhas_csv(source: Any) -> list[dict]:
    """Lê um CSV (caminho, bytes ou file-like) e devolve ``list[dict]``.

    Usa a 1ª linha como cabeçalho (igual ao ``pd.read_csv``) e remove BOM.
    """
    if isinstance(source, (bytes, bytearray)):
        texto = bytes(source).decode("utf-8-sig")
    elif hasattr(source, "read"):
        dados = source.read()
        texto = dados.decode("utf-8-sig") if isinstance(dados, (bytes, bytearray)) else dados
    else:
        with open(Path(source), "r", encoding="utf-8-sig", newline="") as fh:
            texto = fh.read()
    leitor = csv.DictReader(io.StringIO(texto))
    return [dict(linha) for linha in leitor]


def ler_planilha(source: Any, *, nome_arquivo: str = "", header_row: int = 0) -> list[dict]:
    """Lê .xlsx ou .csv (detecta pela extensão do nome) como ``list[dict]``."""
    nome = (nome_arquivo or (source if isinstance(source, (str, Path)) else "")) or ""
    if str(nome).lower().endswith(".csv"):
        return ler_linhas_csv(source)
    return ler_linhas_xlsx(source, header_row=header_row)
