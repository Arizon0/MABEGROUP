"""Models financeiros — Contas a Pagar (Prioridade 4/5).

Lançamento automático a cada pedido de compra aprovado.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

CONTA_ABERTA = "aberto"
CONTA_PAGA = "pago"


class ContaPagar(Base):
    __tablename__ = "contas_a_pagar"

    id: Mapped[int] = mapped_column(primary_key=True)
    fornecedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("fornecedores.id"), nullable=True, index=True
    )
    pedido_compra_id: Mapped[int | None] = mapped_column(
        ForeignKey("pedidos_compra.id"), nullable=True, index=True
    )
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    valor: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    vencimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CONTA_ABERTA)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    pago_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    fornecedor: Mapped["Fornecedor | None"] = relationship()  # noqa: F821
