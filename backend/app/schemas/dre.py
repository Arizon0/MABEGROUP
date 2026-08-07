"""Schemas Pydantic da DRE."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class DespesaUpsert(BaseModel):
    ano: int = Field(..., ge=2000, le=2100)
    mes: int = Field(..., ge=1, le=12)
    grupo: str = Field(..., max_length=30)
    categoria: str = Field(..., max_length=80)
    valor: Decimal = Field(default=Decimal("0"))


class DespesaOut(BaseModel):
    ano: int
    mes: int
    grupo: str
    categoria: str
    valor: Decimal
