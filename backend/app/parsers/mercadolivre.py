"""Parser do relatório de vendas do Mercado Livre.

Arquivo: ``Vendas_BR_MercadoLibre_*.xlsx`` | Aba: ``Vendas BR``.

Pontos críticos (ver "Armadilhas de Parsing" no CLAUDE.md):
  1. O cabeçalho real fica abaixo de algumas linhas de metadados -> ``detectar_header_ml``.
  2. Pacotes multi-produto: 1 linha-resumo (carrega o dinheiro, SKU vazio) +
     N linhas-componente (carregam o SKU, financeiro em branco).
  3. ``Total (BRL)`` já é o líquido final -> importar direto, não recalcular.
  4. Frete líquido = ``Receita por envio`` + ``Tarifas de envio`` (esta última negativa).
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Optional, Union

import openpyxl
import pandas as pd

ZERO = Decimal("0")

from .common import (
    CANAL_ML,
    STATUS_CANCELADO,
    STATUS_DEVOLUCAO,
    STATUS_VALIDO,
    VendaDTO,
    is_empty,
    to_datetime,
    to_decimal,
    to_str,
)

HEADER_MARKER = "N.º de venda"

# Nomes exatos das colunas no arquivo do ML.
COL_ID = "N.º de venda"
COL_DATA = "Data da venda"
COL_ESTADO = "Estado"
COL_SKU = "SKU"
COL_ANUNCIO = "# de anúncio"
COL_TITULO = "Título do anúncio"
COL_TIPO = "Tipo de anúncio"
COL_ENTREGA = "Forma de entrega"
COL_UNIDADES = "Unidades"
COL_PRECO = "Preço unitário de venda do anúncio (BRL)"
COL_RECEITA = "Receita por produtos (BRL)"
COL_TARIFA = "Tarifa de venda e impostos (BRL)"
COL_TARIFA_ENVIO = "Tarifas de envio (BRL)"
COL_RECEITA_ENVIO = "Receita por envio (BRL)"
COL_DESCONTOS = "Descontos e bônus"
COL_CANCELAMENTOS = "Cancelamentos e reembolsos (BRL)"
COL_TOTAL = "Total (BRL)"
COL_PACOTE = "Pacote de diversos produtos"

# Conjuntos de classificação de status (campo status_erp).
# Estados confirmados em export real do ML (jun/2026): ver tests/data_real_states.
CANCELADOS = {
    "Cancelada pelo comprador",
    "Cancelada",
    "Pacote cancelado pelo Mercado Livre",
    "Venda cancelada. Não envie.",
    "Liberamos o dinheiro da venda para você e reembolsamos o comprador",
    # Reembolso ao comprador = venda revertida (descoberto em dados reais).
    "Reclamação encerrada com reembolso para o comprador",
    "Reembolsamos o valor ao comprador",
    # Mediações e reclamações: o cliente decidiu tratar como cancelado (não dão
    # baixa de estoque). Inclui casos em andamento e resolvidos.
    "Mediação com devolução habilitada",
    "Reclamação com devolução habilitada",
    "Mediação finalizada. Te demos o dinheiro.",
    "Liberamos o valor do produto que devolveram para você",
}

# Qualquer estado iniciado por "Devolução" é uma devolução. O ML tem dezenas de
# variações ("Devolução a caminho", "Devolução para revisar até terça-feira",
# "Devolução revisada. Colocamos o produto novamente à venda", ...); casar pelo
# prefixo evita ter de enumerar cada uma. ``DEVOLUCOES_EXTRA`` cobre estados de
# devolução que não começam com a palavra (ex.: "Em devolução").
DEVOLUCAO_PREFIXO = "Devolução"
DEVOLUCOES_EXTRA = {
    "Em devolução",
}


def detectar_header_ml(path: Union[str, Path]) -> int:
    """Retorna o índice 0-based da linha de cabeçalho (para usar em ``header=``).

    Busca a célula que contém ``"N.º de venda"`` nas primeiras 15 linhas.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        for i, row in enumerate(ws.iter_rows(min_row=1, max_row=15, values_only=True)):
            for cell in row:
                if cell and HEADER_MARKER in str(cell):
                    return i
    finally:
        wb.close()
    raise ValueError(
        f"Cabeçalho '{HEADER_MARKER}' não encontrado nas primeiras 15 linhas de {path}"
    )


def classificar_status(estado: str) -> str:
    """Mapeia o ``Estado`` do ML para ``status_erp``."""
    estado = (estado or "").strip()
    if estado in CANCELADOS:
        return STATUS_CANCELADO
    if estado.startswith(DEVOLUCAO_PREFIXO) or estado in DEVOLUCOES_EXTRA:
        return STATUS_DEVOLUCAO
    return STATUS_VALIDO


def classificar_canal_logistico(forma_entrega: str) -> str:
    """Deriva o canal logístico a partir de ``Forma de entrega``."""
    forma = (forma_entrega or "").strip()
    if "Full" in forma:
        return "ML Full"
    if "Flex" in forma:
        return "ML Flex"
    if forma:
        return "ML Agência/Correios"
    return ""


def parse_ml(path: Union[str, Path]) -> list[VendaDTO]:
    """Lê o arquivo do Mercado Livre e retorna uma lista de ``VendaDTO``."""
    header_row = detectar_header_ml(path)
    df = pd.read_excel(path, sheet_name=0, header=header_row, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]
    return _rows_to_dtos(df)


# --------------------------------------------------------------------------- #
# Internos                                                                      #
# --------------------------------------------------------------------------- #


def _get(row: pd.Series, col: str):
    return row[col] if col in row.index else None


def _is_data_row(row: pd.Series) -> bool:
    """Linha de dados real precisa ter ao menos N.º de venda OU SKU."""
    return not is_empty(_get(row, COL_ID)) or not is_empty(_get(row, COL_SKU))


def _is_package_summary(row: pd.Series) -> bool:
    """Linha-resumo de pacote: marcada como pacote e sem SKU próprio."""
    pacote = to_str(_get(row, COL_PACOTE)).lower() == "sim"
    return pacote and is_empty(_get(row, COL_SKU))


def _is_component(row: pd.Series) -> bool:
    """Linha-componente: tem SKU mas o financeiro (Total/Receita) está em branco."""
    tem_sku = not is_empty(_get(row, COL_SKU))
    sem_financeiro = is_empty(_get(row, COL_RECEITA)) and is_empty(_get(row, COL_TOTAL))
    return tem_sku and sem_financeiro


def _rows_to_dtos(df: pd.DataFrame) -> list[VendaDTO]:
    resultado: list[VendaDTO] = []
    n = len(df)
    i = 0
    while i < n:
        row = df.iloc[i]
        if not _is_data_row(row):
            i += 1
            continue

        if _is_package_summary(row):
            financeiro = row
            componentes = []
            j = i + 1
            while j < n and _is_component(df.iloc[j]):
                componentes.append(df.iloc[j])
                j += 1

            # A linha-resumo carrega TODO o dinheiro (sku vazio, sem unidades).
            resultado.append(_build_dto(financeiro, is_summary=True))
            # Cada componente carrega SKU + unidades para baixa de estoque,
            # mas com financeiro zerado para não duplicar o valor do pacote.
            for comp in componentes:
                resultado.append(
                    _build_dto(comp, financeiro_row=financeiro, zero_money=True)
                )
            i = j if componentes else i + 1
        else:
            resultado.append(_build_dto(row))
            i += 1
    return resultado


def _build_dto(
    row: pd.Series,
    *,
    financeiro_row: Optional[pd.Series] = None,
    zero_money: bool = False,
    is_summary: bool = False,
) -> VendaDTO:
    estado = to_str(_get(row, COL_ESTADO))

    id_pedido = to_str(_get(row, COL_ID))
    if not id_pedido and financeiro_row is not None:
        id_pedido = to_str(_get(financeiro_row, COL_ID))

    data = to_datetime(_get(row, COL_DATA))
    if data is None and financeiro_row is not None:
        data = to_datetime(_get(financeiro_row, COL_DATA))

    if not estado and financeiro_row is not None:
        estado = to_str(_get(financeiro_row, COL_ESTADO))

    sku = "" if is_summary else to_str(_get(row, COL_SKU))

    is_pacote = (
        is_summary
        or zero_money
        or to_str(_get(row, COL_PACOTE)).lower() == "sim"
    )

    if zero_money:
        receita = tarifa = frete = descontos = cancelamentos = liquido = ZERO
    else:
        receita = to_decimal(_get(row, COL_RECEITA))
        tarifa = to_decimal(_get(row, COL_TARIFA))  # já negativo no arquivo
        frete = to_decimal(_get(row, COL_RECEITA_ENVIO)) + to_decimal(
            _get(row, COL_TARIFA_ENVIO)
        )  # receita (+) + tarifa (−) = frete líquido
        descontos = to_decimal(_get(row, COL_DESCONTOS))
        cancelamentos = to_decimal(_get(row, COL_CANCELAMENTOS))
        liquido = to_decimal(_get(row, COL_TOTAL))  # já é o líquido final

    return VendaDTO(
        canal=CANAL_ML,
        id_pedido_canal=id_pedido,
        data_venda=data,
        status_canal=estado,
        status_erp=classificar_status(estado),
        sku_canal=sku,
        id_anuncio=to_str(_get(row, COL_ANUNCIO)) or None,
        titulo=to_str(_get(row, COL_TITULO)),
        tipo_anuncio=to_str(_get(row, COL_TIPO)) or None,
        canal_logistico=classificar_canal_logistico(to_str(_get(row, COL_ENTREGA))),
        qtd=to_decimal(_get(row, COL_UNIDADES)),
        preco_unitario=to_decimal(_get(row, COL_PRECO)),
        receita_bruta=receita,
        tarifas_plataforma=tarifa,
        frete_liquido=frete,
        descontos=descontos,
        cancelamentos=cancelamentos,
        liquido_recebido=liquido,
        is_pacote_multi=is_pacote,
    )
