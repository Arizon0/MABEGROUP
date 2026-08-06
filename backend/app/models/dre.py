"""Model das despesas editáveis da DRE mensal.

A DRE é organizada por competência (ano/mês). As receitas e o CMV são
calculados automaticamente a partir das vendas importadas — nunca editáveis.
As **despesas** (operacionais por canal, gerais e deduções de receita) são
lançadas manualmente pelo usuário e persistidas aqui, uma linha por
(ano, mês, grupo, categoria).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

# Grupos de despesa da DRE.
GRUPO_DEDUCOES = "deducoes"            # Cancelamentos, Devoluções, Reembolsos
GRUPO_OPERACIONAL_ML = "operacional_ml"
GRUPO_OPERACIONAL_SHOPEE = "operacional_shopee"
GRUPO_GERAL = "geral"

GRUPOS_OPERACIONAIS = (GRUPO_OPERACIONAL_ML, GRUPO_OPERACIONAL_SHOPEE)


class DespesaDRE(Base):
    """Uma linha editável da DRE de uma competência (ano/mês)."""

    __tablename__ = "dre_despesas"
    __table_args__ = (
        UniqueConstraint("ano", "mes", "grupo", "categoria", name="uq_dre_despesa"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ano: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    mes: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    grupo: Mapped[str] = mapped_column(String(30), nullable=False)
    categoria: Mapped[str] = mapped_column(String(80), nullable=False)
    valor: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
