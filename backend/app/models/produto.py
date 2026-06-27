"""Model de Produto (cadastro mínimo necessário para o SKU Map)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Produto(Base):
    __tablename__ = "produtos"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku_base: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    descricao: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    categoria: Mapped[str | None] = mapped_column(String(120), nullable=True)
    preco_venda: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sku_maps: Mapped[list["SkuMap"]] = relationship(  # noqa: F821
        back_populates="produto", cascade="all, delete-orphan"
    )
