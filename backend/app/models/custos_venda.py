"""Models dos custos que não vêm nas planilhas de venda.

As planilhas do Mercado Livre e da Shopee entregam receita, comissão, frete e
o líquido recebido — mas **não** entregam o imposto sobre a venda nem o quanto
foi investido em publicidade naquele anúncio. Sem esses dois números a margem
por pedido fica otimista e o vendedor acha que ganha dinheiro em venda que na
verdade dá prejuízo.

Este módulo persiste os dois:

``AliquotaImposto``
    Alíquota efetiva (Simples Nacional) por competência, com **vigência**: a
    alíquota de uma venda é a da competência mais recente que seja anterior ou
    igual à data da venda. Assim uma mudança de faixa em agosto não reescreve o
    imposto que já foi apurado em maio.

``AdsInvestimento``
    Investimento em publicidade do mês, lançado no escopo mais granular que o
    relatório do canal permitir (anúncio, SKU ou o canal inteiro), junto com a
    receita que o canal atribuiu à publicidade — a única forma de calcular ACOS
    de verdade. Ver ``services/vendas_analise.py`` para o rateio.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

# Escopos de lançamento de Ads, do mais específico para o mais genérico.
# A ordem desta tupla é a ordem de precedência aplicada no rateio.
ESCOPO_ANUNCIO = "anuncio"
ESCOPO_SKU = "sku"
ESCOPO_CANAL = "canal"
ESCOPOS_ADS = (ESCOPO_ANUNCIO, ESCOPO_SKU, ESCOPO_CANAL)


class AliquotaImposto(Base):
    """Alíquota efetiva de imposto sobre a venda, vigente a partir de (ano, mês)."""

    __tablename__ = "aliquotas_imposto"
    __table_args__ = (UniqueConstraint("ano", "mes", name="uq_aliquota_competencia"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ano: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    mes: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # Alíquota efetiva já calculada pela contabilidade (ex.: 8.22 = 8,22%).
    aliquota_pct: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    observacao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AdsInvestimento(Base):
    """Investimento em publicidade de uma competência, em um escopo."""

    __tablename__ = "ads_investimento"
    __table_args__ = (
        UniqueConstraint(
            "canal", "ano", "mes", "escopo", "referencia", name="uq_ads_escopo"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    canal: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    ano: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    mes: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    escopo: Mapped[str] = mapped_column(String(10), nullable=False, default=ESCOPO_CANAL)
    # id_anuncio quando escopo='anuncio'; sku_base quando escopo='sku'; vazio
    # quando escopo='canal'. Fica '' (e não NULL) porque em Postgres duas linhas
    # com NULL não colidem no UNIQUE — o que permitiria duplicar o lançamento
    # do canal inteiro e dobrar o investimento rateado.
    referencia: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    # Quanto foi gasto em publicidade no escopo, na competência.
    valor: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    # Receita que o canal atribuiu à publicidade. Só o relatório de Ads sabe
    # disso; sem ela o ACOS é indeterminado (e a tela mostra "—").
    receita_ads: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
