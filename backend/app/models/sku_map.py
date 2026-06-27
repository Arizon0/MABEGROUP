"""Models do de-para de SKUs e das pendências de mapeamento."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class SkuMap(Base):
    """De-para: código do canal (sku_canal + canal) -> produto/sku_base do ERP."""

    __tablename__ = "sku_map"
    __table_args__ = (UniqueConstraint("sku_canal", "canal", name="uq_sku_canal_canal"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sku_canal: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    canal: Mapped[str] = mapped_column(String(20), nullable=False)  # 'Mercado Livre' | 'Shopee'
    id_anuncio: Mapped[str | None] = mapped_column(String(50), nullable=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    sku_base: Mapped[str] = mapped_column(String(50), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    produto: Mapped["Produto"] = relationship(back_populates="sku_maps")  # noqa: F821


class SkuPendencia(Base):
    """SKU de canal encontrado em uma importação que ainda não tem de-para.

    Não bloqueia a importação (regra 4 do CLAUDE.md): registra-se a pendência
    para resolução posterior na tela "Mapa de SKUs".
    """

    __tablename__ = "sku_pendencias"
    __table_args__ = (
        UniqueConstraint("sku_canal", "canal", name="uq_pendencia_sku_canal"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sku_canal: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    canal: Mapped[str] = mapped_column(String(20), nullable=False)
    id_anuncio: Mapped[str | None] = mapped_column(String(50), nullable=True)
    titulo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ocorrencias: Mapped[int] = mapped_column(default=1, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
