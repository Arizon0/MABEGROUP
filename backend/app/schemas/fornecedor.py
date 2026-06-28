"""Schemas Pydantic do cadastro de Fornecedores (Prioridade 2)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.validators import normalizar_cnpj, validar_cnpj


class ContatoBase(BaseModel):
    nome: str = Field(..., max_length=120)
    cargo: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None


class ContatoOut(ContatoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class FornecedorBase(BaseModel):
    razao_social: str = Field(..., max_length=255)
    nome_fantasia: Optional[str] = None
    inscricao_estadual: Optional[str] = None
    logradouro: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    uf: Optional[str] = Field(None, max_length=2)
    cep: Optional[str] = None
    condicoes_pagamento_dias: Optional[int] = None
    prazo_medio_entrega_dias: Optional[int] = None


class FornecedorCreate(FornecedorBase):
    cnpj: str = Field(..., description="CNPJ com ou sem máscara")
    contatos: list[ContatoBase] = []

    @field_validator("cnpj")
    @classmethod
    def _validar_cnpj(cls, v: str) -> str:
        if not validar_cnpj(v):
            raise ValueError("CNPJ inválido (dígito verificador não confere)")
        return normalizar_cnpj(v)


class FornecedorUpdate(FornecedorBase):
    razao_social: Optional[str] = None  # tudo opcional na edição


class FornecedorOut(FornecedorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cnpj: str
    criado_em: Optional[datetime] = None
    contatos: list[ContatoOut] = []
