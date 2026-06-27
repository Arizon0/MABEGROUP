"""Models de Estoque Multi-local (Prioridade 3).

- ``Local``: galpão, fulfillment do canal, escritório, etc.
- ``EstoqueSaldo``: saldo por produto × local (disponível, reservado, custo médio).
- ``MovimentoEstoque``: razão (ledger) de toda entrada/saída/reserva, base para
  custo médio ponderado e relatórios.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

# Tipos de local
LOCAL_GALPAO = "galpao"
LOCAL_FULFILLMENT = "fulfillment"
LOCAL_ESCRITORIO = "escritorio"

# Tipos de movimento
MOV_ENTRADA = "entrada"            # recebimento de compra / ajuste positivo
MOV_SAIDA = "saida"                # venda / ajuste negativo
MOV_RESERVA = "reserva"            # move disponível -> reservada
MOV_LIBERACAO = "liberacao"        # move reservada -> disponível
MOV_TRANSFERENCIA = "transferencia"


class Local(Base):
    __tablename__ = "locais"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default=LOCAL_GALPAO)
    descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ativo: Mapped[bool] = mapped_column(default=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    saldos: Mapped[list["EstoqueSaldo"]] = relationship(back_populates="local")


class EstoqueSaldo(Base):
    __tablename__ = "estoque_saldo"
    __table_args__ = (
        UniqueConstraint("produto_id", "local_id", name="uq_saldo_produto_local"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    local_id: Mapped[int] = mapped_column(
        ForeignKey("locais.id"), nullable=False, index=True
    )
    qtd_disponivel: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, default=0)
    qtd_reservada: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, default=0)
    custo_medio: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)

    produto: Mapped["Produto"] = relationship()  # noqa: F821
    local: Mapped["Local"] = relationship(back_populates="saldos")


class MovimentoEstoque(Base):
    __tablename__ = "movimentos_estoque"

    id: Mapped[int] = mapped_column(primary_key=True)
    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    local_id: Mapped[int] = mapped_column(ForeignKey("locais.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    qtd: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    custo_unitario: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    origem: Mapped[str | None] = mapped_column(String(30), nullable=True)  # compra|venda|manual|importacao
    referencia: Mapped[str | None] = mapped_column(String(80), nullable=True)
    observacao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
