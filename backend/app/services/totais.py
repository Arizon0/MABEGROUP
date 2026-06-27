"""Agregação de totais a partir de uma lista de ``VendaDTO``.

Reutilizado pelos testes de validação, pelo retorno da importação e (futuramente)
pelo dashboard. Tudo em ``Decimal``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

from app.parsers.common import VendaDTO

ZERO = Decimal("0")


@dataclass
class Totais:
    linhas: int = 0
    unidades: Decimal = field(default_factory=lambda: ZERO)
    receita_bruta: Decimal = field(default_factory=lambda: ZERO)
    tarifas_plataforma: Decimal = field(default_factory=lambda: ZERO)
    frete_liquido: Decimal = field(default_factory=lambda: ZERO)
    descontos: Decimal = field(default_factory=lambda: ZERO)
    cancelamentos: Decimal = field(default_factory=lambda: ZERO)
    liquido_recebido: Decimal = field(default_factory=lambda: ZERO)

    def as_dict(self) -> dict:
        return {
            "linhas": self.linhas,
            "unidades": str(self.unidades),
            "receita_bruta": str(self.receita_bruta),
            "tarifas_plataforma": str(self.tarifas_plataforma),
            "frete_liquido": str(self.frete_liquido),
            "descontos": str(self.descontos),
            "cancelamentos": str(self.cancelamentos),
            "liquido_recebido": str(self.liquido_recebido),
        }


def calcular_totais(vendas: Iterable[VendaDTO]) -> Totais:
    """Soma os campos financeiros de uma lista de vendas.

    ``linhas`` conta as linhas de pedido (resumo de pacote conta como 1 linha;
    componentes não contam como pedido). ``unidades`` soma ``qtd``.
    """
    t = Totais()
    for v in vendas:
        # Linhas-componente de pacote (financeiro zerado) não representam um
        # "pedido" separado — somam unidades mas não contam como linha de pedido.
        if not _is_componente_pacote(v):
            t.linhas += 1
        t.unidades += v.qtd
        t.receita_bruta += v.receita_bruta
        t.tarifas_plataforma += v.tarifas_plataforma
        t.frete_liquido += v.frete_liquido
        t.descontos += v.descontos
        t.cancelamentos += v.cancelamentos
        t.liquido_recebido += v.liquido_recebido
    return t


def _is_componente_pacote(v: VendaDTO) -> bool:
    """Componente de pacote: parte de um multi-pacote, com SKU e financeiro zerado."""
    return (
        v.is_pacote_multi
        and bool(v.sku_canal)
        and v.liquido_recebido == ZERO
        and v.receita_bruta == ZERO
    )
