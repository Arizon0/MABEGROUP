"""Anexos genéricos (até 5 por produto e por fornecedor).

Usa um vínculo polimórfico simples (owner_tipo + owner_id) para evitar duas
tabelas quase idênticas. O limite de 5 anexos é aplicado na camada de serviço.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

OWNER_PRODUTO = "produto"
OWNER_FORNECEDOR = "fornecedor"
OWNER_PEDIDO_COMPRA = "pedido_compra"
MAX_ANEXOS = 5


class Anexo(Base):
    __tablename__ = "anexos"
    __table_args__ = (Index("ix_anexo_owner", "owner_tipo", "owner_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # 'produto'|'fornecedor'
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    nome_arquivo: Mapped[str] = mapped_column(String(255), nullable=False)
    categoria: Mapped[str | None] = mapped_column(String(60), nullable=True)  # ficha_tecnica, nf, contrato...
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    caminho: Mapped[str] = mapped_column(String(512), nullable=False)
    tamanho_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
