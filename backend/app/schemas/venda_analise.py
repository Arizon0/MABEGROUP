"""Schemas Pydantic da análise venda-a-venda e dos custos que a alimentam."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.custos_venda import ESCOPO_CANAL, ESCOPOS_ADS


class AliquotaUpsert(BaseModel):
    """Alíquota efetiva de imposto vigente a partir de (ano, mês)."""

    ano: int = Field(..., ge=2000, le=2100)
    mes: int = Field(..., ge=1, le=12)
    aliquota_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    observacao: str | None = Field(default=None, max_length=255)


class AliquotaOut(BaseModel):
    id: int
    ano: int
    mes: int
    aliquota_pct: Decimal
    observacao: str | None = None


class AdsUpsert(BaseModel):
    """Investimento em publicidade de uma competência, em um escopo."""

    canal: str = Field(..., max_length=20)
    ano: int = Field(..., ge=2000, le=2100)
    mes: int = Field(..., ge=1, le=12)
    escopo: str = Field(default=ESCOPO_CANAL, max_length=10)
    referencia: str = Field(default="", max_length=60)
    valor: Decimal = Field(default=Decimal("0"), ge=0)
    # Receita que o canal atribuiu à publicidade. Sem ela não há ACOS — só TACOS.
    receita_ads: Decimal | None = Field(default=None, ge=0)

    @field_validator("escopo")
    @classmethod
    def _escopo_valido(cls, v: str) -> str:
        if v not in ESCOPOS_ADS:
            raise ValueError(f"escopo deve ser um de {list(ESCOPOS_ADS)}")
        return v

    @field_validator("referencia")
    @classmethod
    def _referencia_limpa(cls, v: str | None) -> str:
        return (v or "").strip()


class AdsOut(BaseModel):
    id: int
    canal: str
    ano: int
    mes: int
    escopo: str
    referencia: str
    valor: Decimal
    receita_ads: Decimal | None = None


class NotaFiscalUpsert(BaseModel):
    """Número da NF de um pedido, quando o export do canal não o traz."""

    canal: str = Field(..., max_length=20)
    id_pedido_canal: str = Field(..., max_length=50)
    numero_nf: str | None = Field(default=None, max_length=30)

    @field_validator("numero_nf")
    @classmethod
    def _nf_limpa(cls, v: str | None) -> str | None:
        limpo = (v or "").strip()
        return limpo or None
