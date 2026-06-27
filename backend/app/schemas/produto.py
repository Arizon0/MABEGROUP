"""Schemas Pydantic do cadastro de Produtos (Prioridade 2)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProdutoBase(BaseModel):
    nome: str = Field(..., max_length=255)
    descricao: Optional[str] = None
    categoria: Optional[str] = None
    subcategoria: Optional[str] = None
    atributos: Optional[dict[str, Any]] = None
    unidade_medida: str = "UN"
    peso_kg: Optional[Decimal] = None
    comprimento_cm: Optional[Decimal] = None
    largura_cm: Optional[Decimal] = None
    altura_cm: Optional[Decimal] = None
    ncm: Optional[str] = Field(None, max_length=10)
    aliquota_icms: Optional[Decimal] = None
    aliquota_pis: Optional[Decimal] = None
    aliquota_cofins: Optional[Decimal] = None
    aliquota_ipi: Optional[Decimal] = None
    estoque_minimo: Decimal = Decimal("0")
    estoque_seguranca: Decimal = Decimal("0")
    preco_compra: Optional[Decimal] = None
    preco_venda: Optional[Decimal] = None
    fornecedor_padrao_id: Optional[int] = None
    produto_pai_id: Optional[int] = None


class ProdutoCreate(ProdutoBase):
    sku_base: str = Field(..., max_length=50)


class ProdutoUpdate(BaseModel):
    """Todos os campos opcionais para edição parcial."""

    model_config = ConfigDict(extra="ignore")

    nome: Optional[str] = None
    descricao: Optional[str] = None
    categoria: Optional[str] = None
    subcategoria: Optional[str] = None
    atributos: Optional[dict[str, Any]] = None
    unidade_medida: Optional[str] = None
    peso_kg: Optional[Decimal] = None
    comprimento_cm: Optional[Decimal] = None
    largura_cm: Optional[Decimal] = None
    altura_cm: Optional[Decimal] = None
    ncm: Optional[str] = None
    aliquota_icms: Optional[Decimal] = None
    aliquota_pis: Optional[Decimal] = None
    aliquota_cofins: Optional[Decimal] = None
    aliquota_ipi: Optional[Decimal] = None
    estoque_minimo: Optional[Decimal] = None
    estoque_seguranca: Optional[Decimal] = None
    preco_compra: Optional[Decimal] = None
    preco_venda: Optional[Decimal] = None
    fornecedor_padrao_id: Optional[int] = None
    produto_pai_id: Optional[int] = None


class VarianteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku_base: str
    nome: str
    preco_venda: Optional[Decimal] = None


class ProdutoOut(ProdutoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku_base: str
    criado_em: Optional[datetime] = None
    variantes: list[VarianteOut] = []
