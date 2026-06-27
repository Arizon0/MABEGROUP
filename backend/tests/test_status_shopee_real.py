"""Regressão da classificação/zeragem de status da Shopee com dados REAIS.

Status extraídos de exports reais (abr–jun/2026, 341 linhas). Confirma que:
- 'Cancelado' (único status de cancelamento presente) zera qtd/receita/líquido;
- 'O comprador pode pedir uma devolução até <data>' = janela de devolução ABERTA
  (venda ainda válida, não devolvida) permanece válido;
- status em inglês ('Order Received') e demais ('Concluído', 'Entregue',
  'Enviado') permanecem válidos.
"""
from decimal import Decimal

from app.parsers.common import STATUS_CANCELADO, STATUS_VALIDO
from app.parsers.shopee import _build_dto

# Status reais que devem permanecer VÁLIDOS.
VALIDOS_REAIS = [
    "Concluído",
    "Entregue",
    "Enviado",
    "Order Received",
    "O comprador pode pedir uma devolução até 2026-06-29",
    "O comprador pode pedir uma devolução até 2026-07-03",
]

# Status reais que devem ZERAR e virar Cancelado.
CANCELADOS_REAIS = [
    "Cancelado",
    "Não pago",
]


def _row(status: str) -> dict:
    return {
        "ID do pedido": "SP-1",
        "Data de criação do pedido": "2026-06-10 12:00",
        "Status do pedido": status,
        "Número de referência SKU": "5338",
        "Nome do Produto": "Retentor",
        "Quantidade": 2,
        "Preço acordado": "10.00",
        "Subtotal do produto": "20.00",
        "Taxa de comissão líquida": "2.00",
        "Taxa de serviço líquida": "1.00",
        "Taxa de transação": "0.50",
        "Taxa de Envio Reversa": "0",
    }


def test_shopee_status_validos_reais():
    for status in VALIDOS_REAIS:
        dto = _build_dto(_row(status))
        assert dto.status_erp == STATUS_VALIDO, status
        assert dto.qtd == Decimal("2"), status
        assert dto.receita_bruta == Decimal("20.00"), status
        # líquido = 20 - 2 - 1 - 0.5 - 0 = 16.50
        assert dto.liquido_recebido == Decimal("16.50"), status


def test_shopee_status_cancelados_reais():
    for status in CANCELADOS_REAIS:
        dto = _build_dto(_row(status))
        assert dto.status_erp == STATUS_CANCELADO, status
        assert dto.qtd == Decimal("0"), status
        assert dto.receita_bruta == Decimal("0"), status
        assert dto.liquido_recebido == Decimal("0"), status
