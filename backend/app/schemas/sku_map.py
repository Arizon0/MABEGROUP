"""Schemas Pydantic do módulo SKU Map."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProdutoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku_base: str
    nome: str


class SkuMapBase(BaseModel):
    sku_canal: str = Field(..., max_length=50)
    canal: str = Field(..., max_length=20)  # 'Mercado Livre' | 'Shopee'
    id_anuncio: Optional[str] = Field(None, max_length=50)


class SkuMapCreate(SkuMapBase):
    """Cria/atualiza um de-para. Aceita produto_id OU sku_base."""

    produto_id: Optional[int] = None
    sku_base: Optional[str] = None


class SkuMapOut(SkuMapBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    produto_id: int
    sku_base: str
    criado_em: Optional[datetime] = None


class SkuPendenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku_canal: str
    canal: str
    id_anuncio: Optional[str] = None
    titulo: Optional[str] = None
    ocorrencias: int
