"""Schemas Pydantic da autenticação."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    senha: str = Field(..., min_length=1)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nome: str
    perfil: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class TrocaSenha(BaseModel):
    """Troca de senha do próprio usuário autenticado."""

    senha_atual: str = Field(..., min_length=1)
    senha_nova: str = Field(..., min_length=8, max_length=128)
