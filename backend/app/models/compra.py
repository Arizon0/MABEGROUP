"""Models de Pedido de Compra (Prioridade 4).

Fluxo: ``rascunho`` -> ``aprovado`` -> ``recebido``.
- Ao aprovar: gera lançamento em ``contas_a_pagar``.
- Ao receber: incrementa o estoque (custo médio ponderado) e permite anexar NF.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

PEDIDO_RASCUNHO = "rascunho"
PEDIDO_APROVADO = "aprovado"
PEDIDO_RECEBIDO = "recebido"
PEDIDO_CANCELADO = "cancelado"


class PedidoCompra(Base):
    __tablename__ = "pedidos_compra"

    id: Mapped[int] = mapped_column(primary_key=True)
    fornecedor_id: Mapped[int] = mapped_column(
        ForeignKey("fornecedores.id"), nullable=False, index=True
    )
    local_id: Mapped[int | None] = mapped_column(
        ForeignKey("locais.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PEDIDO_RASCUNHO)
    observacao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    aprovado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recebido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    fornecedor: Mapped["Fornecedor"] = relationship()  # noqa: F821
    itens: Mapped[list["ItemPedidoCompra"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan"
    )

    @property
    def total(self) -> Decimal:
        return sum((item.subtotal for item in self.itens), Decimal("0"))


class ItemPedidoCompra(Base):
    __tablename__ = "itens_pedido_compra"

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(
        ForeignKey("pedidos_compra.id", ondelete="CASCADE"), nullable=False, index=True
    )
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    qtd: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, default=0)
    custo_unitario: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)

    pedido: Mapped["PedidoCompra"] = relationship(back_populates="itens")
    produto: Mapped["Produto"] = relationship()  # noqa: F821

    @property
    def subtotal(self) -> Decimal:
        qtd = self.qtd if isinstance(self.qtd, Decimal) else Decimal(str(self.qtd or 0))
        custo = (
            self.custo_unitario
            if isinstance(self.custo_unitario, Decimal)
            else Decimal(str(self.custo_unitario or 0))
        )
        return qtd * custo
