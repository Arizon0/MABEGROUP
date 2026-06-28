"""Schemas Pydantic dos Pedidos de Compra (Prioridade 4)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ItemCompraIn(BaseModel):
    produto_id: int
    qtd: Decimal = Field(..., gt=0)
    custo_unitario: Decimal = Decimal("0")


class ItemCompraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    produto_id: int
    qtd: Decimal
    custo_unitario: Decimal
    subtotal: Decimal


class PedidoCompraCreate(BaseModel):
    fornecedor_id: int
    itens: list[ItemCompraIn] = Field(..., min_length=1)
    observacao: Optional[str] = None
    local_id: Optional[int] = None


class PedidoCompraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fornecedor_id: int
    local_id: Optional[int] = None
    status: str
    observacao: Optional[str] = None
    criado_em: Optional[datetime] = None
    aprovado_em: Optional[datetime] = None
    recebido_em: Optional[datetime] = None
    total: Decimal
    itens: list[ItemCompraOut] = []


class ReceberIn(BaseModel):
    local_id: Optional[int] = None


class ContaPagarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fornecedor_id: Optional[int] = None
    pedido_compra_id: Optional[int] = None
    descricao: str
    valor: Decimal
    vencimento: Optional[date] = None
    status: str


class SugestaoCompraOut(BaseModel):
    produto_id: int
    sku_base: str
    nome: str
    media_mensal: Decimal
    estoque_minimo: Decimal
    qtd_pendente: Decimal
    qtd_atual: Decimal
    qtd_sugerida: Decimal
    repor: bool
