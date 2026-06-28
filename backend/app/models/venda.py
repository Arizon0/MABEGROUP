"""Model de Venda importada (linha normalizada persistida)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Venda(Base):
    """Linha de venda importada de um canal, já no schema unificado.

    Duplicidade de importação é detectada por (canal, id_pedido_canal) na
    camada de serviço — pacotes multi-produto compartilham o mesmo
    id_pedido_canal, por isso não há UNIQUE rígido nessa dupla.
    """

    __tablename__ = "vendas"
    __table_args__ = (
        Index("ix_venda_pedido_canal", "canal", "id_pedido_canal"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    canal: Mapped[str] = mapped_column(String(20), nullable=False)
    id_pedido_canal: Mapped[str] = mapped_column(String(50), nullable=False)
    data_venda: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status_canal: Mapped[str] = mapped_column(String(255), default="")
    status_erp: Mapped[str] = mapped_column(String(20), default="Válido")
    sku_canal: Mapped[str] = mapped_column(String(50), default="")
    sku_base: Mapped[str | None] = mapped_column(String(50), nullable=True)
    id_anuncio: Mapped[str | None] = mapped_column(String(50), nullable=True)
    titulo: Mapped[str] = mapped_column(String(255), default="")
    tipo_anuncio: Mapped[str | None] = mapped_column(String(20), nullable=True)
    canal_logistico: Mapped[str] = mapped_column(String(40), default="")
    variacao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qtd: Mapped[float] = mapped_column(Numeric(10, 3), default=0)
    preco_unitario: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    receita_bruta: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    tarifas_plataforma: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    frete_liquido: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    descontos: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    cancelamentos: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    liquido_recebido: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    is_pacote_multi: Mapped[bool] = mapped_column(Boolean, default=False)
    importado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
