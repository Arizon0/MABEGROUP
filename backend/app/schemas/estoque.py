"""Schemas Pydantic do módulo de Estoque (Prioridade 3)."""
from __future__ import annotations

from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class LocalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    tipo: str
    ativo: bool


class SaldoOut(BaseModel):
    produto_id: int
    sku_base: str
    nome_produto: str
    local_id: int
    local_nome: str
    qtd_disponivel: Decimal
    qtd_reservada: Decimal
    custo_medio: Decimal
    valor_total: Decimal


class MovimentoIn(BaseModel):
    produto_id: int
    local_id: int
    tipo: Literal["entrada", "saida", "reserva", "liberacao"]
    qtd: Decimal
    custo_unitario: Optional[Decimal] = None
    referencia: Optional[str] = None
    observacao: Optional[str] = None


class SaldoSimplesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    produto_id: int
    local_id: int
    qtd_disponivel: Decimal
    qtd_reservada: Decimal
    custo_medio: Decimal


class AlertaOut(BaseModel):
    produto_id: int
    sku_base: str
    nome: str
    disponivel_total: Decimal
    estoque_minimo: Decimal


class RankingItemOut(BaseModel):
    sku_base: Optional[str]
    unidades: Decimal
    liquido: Decimal


class RelatorioEstoqueOut(BaseModel):
    valor_total_estoque: Decimal
    total_alertas: int
    alertas: list[AlertaOut]
    ranking_skus: list[RankingItemOut]
