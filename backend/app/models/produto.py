"""Model de Produto — cadastro completo (Prioridade 2).

Suporta variantes (produto-pai com N variantes, cada uma com sku_base e estoque
próprios), fornecedor padrão, atributos livres (JSON), fiscais (NCM/alíquotas) e
anexos (via tabela ``anexos``, limitado a 5 na camada de serviço).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Produto(Base):
    __tablename__ = "produtos"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku_base: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    descricao: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Classificação
    categoria: Mapped[str | None] = mapped_column(String(120), nullable=True)
    subcategoria: Mapped[str | None] = mapped_column(String(120), nullable=True)
    atributos: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Logística / medidas
    unidade_medida: Mapped[str] = mapped_column(String(10), nullable=False, default="UN")
    peso_kg: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    comprimento_cm: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    largura_cm: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    altura_cm: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Fiscal
    ncm: Mapped[str | None] = mapped_column(String(10), nullable=True)
    aliquota_icms: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    aliquota_pis: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    aliquota_cofins: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    aliquota_ipi: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Estoque / preços
    estoque_minimo: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, default=0)
    estoque_seguranca: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, default=0)
    preco_compra: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    preco_venda: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Fornecedor padrão
    fornecedor_padrao_id: Mapped[int | None] = mapped_column(
        ForeignKey("fornecedores.id"), nullable=True, index=True
    )

    # Variantes (auto-relacionamento)
    produto_pai_id: Mapped[int | None] = mapped_column(
        ForeignKey("produtos.id"), nullable=True, index=True
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    fornecedor_padrao: Mapped["Fornecedor | None"] = relationship(  # noqa: F821
        back_populates="produtos"
    )
    variantes: Mapped[list["Produto"]] = relationship(
        back_populates="produto_pai", cascade="all, delete-orphan"
    )
    produto_pai: Mapped["Produto | None"] = relationship(
        back_populates="variantes", remote_side="Produto.id"
    )
    sku_maps: Mapped[list["SkuMap"]] = relationship(  # noqa: F821
        back_populates="produto", cascade="all, delete-orphan"
    )
