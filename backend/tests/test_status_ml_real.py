"""Regressão da classificação de status do ML contra os estados REAIS.

Os estados abaixo foram extraídos de um export real da loja (jun/2026, 1029
linhas, 41 estados distintos). Vários deles não existiam nos dados sintéticos e
escapavam como "Válido" — o que causaria baixa indevida de estoque para
devoluções/reembolsos. Este teste fixa o comportamento esperado.
"""
from app.parsers.common import (
    STATUS_CANCELADO,
    STATUS_DEVOLUCAO,
    STATUS_VALIDO,
)
from app.parsers.mercadolivre import classificar_status

# Estados reais → status_erp esperado.
CANCELADOS_REAIS = [
    "Cancelada pelo comprador",
    "Cancelada",
    "Pacote cancelado pelo Mercado Livre",
    "Venda cancelada. Não envie.",
    "Liberamos o dinheiro da venda para você e reembolsamos o comprador",
    # Reembolso ao comprador = venda revertida.
    "Reclamação encerrada com reembolso para o comprador",
    "Reembolsamos o valor ao comprador",
    # Mediações/reclamações: decisão do cliente = tratar como cancelado.
    "Mediação com devolução habilitada",
    "Reclamação com devolução habilitada",
    "Mediação finalizada. Te demos o dinheiro.",
    "Liberamos o valor do produto que devolveram para você",
]

DEVOLUCOES_REAIS = [
    "Devolução a caminho",
    "Devolução a caminho. Vamos revisar o produto",
    "Devolução em preparação",
    "Devolução em preparação sem custo de envio",
    "Devolução finalizada. Colocamos o produto à venda novamente",
    "Devolução finalizada. Colocamos os produtos à venda novamente",
    "Devolução finalizada com reembolso para o comprador",
    "Devolução revisada. Solicite a retirada do produto",
    "Devolução revisada. Colocamos o produto novamente à venda",
    # Variações que NÃO casavam com a lista antiga (prefixo fixo):
    "Devolução para revisar até terça-feira",
    "Devolução para revisar até quarta-feira",
    "Em devolução",
]

# Estados que permanecem válidos: vendas concluídas ou em andamento de envio.
VALIDOS_REAIS = [
    "Entregue",
    "Venda entregue",
    "A caminho",
    "Processando no centro de distribuição",
    "No ponto de retirada",
    "Vamos enviar o pacote no dia 29 de junho",
    "Para enviar no dia 7 de julho",
    "Chega entre os dias 29 jun e 1 jul",
    "Pacote de 2 produtos",
]


def test_estados_cancelados_reais():
    for estado in CANCELADOS_REAIS:
        assert classificar_status(estado) == STATUS_CANCELADO, estado


def test_estados_devolucao_reais():
    for estado in DEVOLUCOES_REAIS:
        assert classificar_status(estado) == STATUS_DEVOLUCAO, estado


def test_estados_validos_reais():
    for estado in VALIDOS_REAIS:
        assert classificar_status(estado) == STATUS_VALIDO, estado


def test_devolucao_por_prefixo_generico():
    # Qualquer estado novo iniciado por "Devolução" deve ser tratado como tal.
    assert classificar_status("Devolução qualquer coisa nova") == STATUS_DEVOLUCAO


def test_estado_vazio_e_valido():
    assert classificar_status("") == STATUS_VALIDO
    assert classificar_status(None) == STATUS_VALIDO  # type: ignore[arg-type]
