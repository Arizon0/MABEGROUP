"""Geradores de planilhas sintéticas que exercitam as armadilhas de parsing.

Cada gerador retorna ``(caminho, esperado)`` onde ``esperado`` é um dict com os
totais calculados à mão, para servir de assertion nos testes de parser.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

D = Decimal


def _write_xlsx(path: Path, headers: list[str], rows: list[list], leading: int = 0) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Planilha"
    # Linhas de metadados antes do cabeçalho (simula export do ML).
    for n in range(leading):
        ws.append([f"Relatório de vendas — linha de metadados {n + 1}"])
    ws.append(headers)
    for row in rows:
        ws.append(row)
    wb.save(path)


# --------------------------------------------------------------------------- #
# Mercado Livre                                                                 #
# --------------------------------------------------------------------------- #

ML_HEADERS = [
    "N.º de venda",
    "Data da venda",
    "Estado",
    "SKU",
    "# de anúncio",
    "Título do anúncio",
    "Tipo de anúncio",
    "Forma de entrega",
    "Unidades",
    "Preço unitário de venda do anúncio (BRL)",
    "Receita por produtos (BRL)",
    "Tarifa de venda e impostos (BRL)",
    "Tarifas de envio (BRL)",
    "Receita por envio (BRL)",
    "Descontos e bônus",
    "Cancelamentos e reembolsos (BRL)",
    "Total (BRL)",
    "Pacote de diversos produtos",
]


def build_ml_xlsx(path: Path, leading_meta: int = 5) -> tuple[Path, dict]:
    """Cria um arquivo ML com: venda normal, cancelada, devolução, pacote multi
    (resumo + 2 componentes) e linha sem SKU. ``leading_meta`` linhas de
    metadados antes do cabeçalho (header esperado no índice == leading_meta).
    """
    rows = [
        # V1 — normal, ML Full, Premium
        ["V1", "2026-05-10 10:00", "Entregue", "5338", "MLB6527593792",
         "Retentor Volante", "Premium", "Mercado Envios Full", 2, 50,
         100, -15, -5, 0, 0, 0, 80, "Não"],
        # V2 — cancelada, ML Flex
        ["V2", "2026-05-11 11:00", "Cancelada pelo comprador", "8126", "MLB4672105869",
         "Jogo Anel", "Clássico", "Mercado Envios Flex", 1, 120,
         120, -18, 0, 0, 0, -120, -18, "Não"],
        # V3 — RESUMO de pacote (carrega o dinheiro, SKU vazio)
        ["V3", "2026-05-12 09:00", "Pacote de 2 produtos", None, None,
         "Pacote", None, "Mercado Envios Full", None, None,
         200, -30, -10, 0, 5, 0, 165, "Sim"],
        # V3a — componente (SKU + unidades, financeiro em branco)
        ["V3", None, None, "5245", "MLB6756962850",
         "Retentor Palio", "Premium", None, 3, None,
         None, None, None, None, None, None, None, "Sim"],
        # V3b — componente
        ["V3", None, None, "5699", None,
         "Retentor Liso", None, None, 1, None,
         None, None, None, None, None, None, None, "Sim"],
        # V4 — devolução
        ["V4", "2026-05-13 14:00", "Devolução finalizada", "5245", "MLB6756962850",
         "Retentor Palio", "Premium", "Mercado Envios Full", 1, 70,
         70, -10, -4, 0, 0, 0, 56, "Não"],
        # V5 — normal sem SKU (não é pacote)
        ["V5", "2026-05-14 16:00", "Entregue", None, "MLB0000000000",
         "Produto sem sku", "Clássico", "Mercado Envios Full", 1, 40,
         40, -6, -2, 0, 0, 0, 32, "Não"],
    ]
    _write_xlsx(path, ML_HEADERS, rows, leading=leading_meta)

    esperado = {
        "header_index": leading_meta,
        "dtos": 7,
        "linhas": 5,
        "unidades": D("9"),
        "receita_bruta": D("530"),
        "tarifas_plataforma": D("-79"),
        "frete_liquido": D("-21"),
        "descontos": D("5"),
        "cancelamentos": D("-120"),
        "liquido_recebido": D("315"),
    }
    return path, esperado


# --------------------------------------------------------------------------- #
# Shopee                                                                        #
# --------------------------------------------------------------------------- #

SHOPEE_HEADERS = [
    "ID do pedido",
    "Data de criação do pedido",
    "Status do pedido",
    "Número de referência SKU",
    "Nº de referência do SKU principal",
    "Nome do Produto",
    "Nome da variação",
    "Preço acordado",
    "Quantidade",
    "Subtotal do produto",
    "Taxa de comissão líquida",
    "Taxa de serviço líquida",
    "Taxa de transação",
    "Taxa de Envio Reversa",
]


def build_shopee_xlsx(path: Path) -> tuple[Path, dict]:
    """Cria um arquivo Shopee com: pedido válido, cancelado, não pago e um
    pedido que usa o SKU de fallback (coluna principal vazia)."""
    rows = [
        # S1 — válido
        ["S1", "2026-05-10 10:00", "Concluído", "5338", "",
         "Retentor", "Tamanho único", 50, 2, 100, 8, 4, 2, 0],
        # S2 — cancelado (valores preenchidos no arquivo, devem zerar) + fallback SKU
        ["S2", "2026-05-11 11:00", "Cancelado", "", "8126STA",
         "Jogo Anel", "STD", 50, 1, 50, 5, 2, 1, 0],
        # S3 — não pago (zerar)
        ["S3", "2026-05-12 12:00", "Não pago", "5245", "",
         "Retentor Palio", "", 40, 1, 40, 4, 2, 1, 0],
        # S4 — válido usando fallback de SKU
        ["S4", "2026-05-13 13:00", "Concluído", "", "2178",
         "Retentor 2178", "", 30, 1, 30, 3, 1, 1, 0],
    ]
    _write_xlsx(path, SHOPEE_HEADERS, rows, leading=0)

    esperado = {
        "dtos": 4,
        "linhas": 4,
        "unidades": D("3"),
        "receita_bruta": D("130"),
        "tarifas_plataforma": D("-19"),
        "frete_liquido": D("0"),
        "descontos": D("0"),
        "cancelamentos": D("0"),
        "liquido_recebido": D("111"),
    }
    return path, esperado
