"""Schemas Pydantic do cadastro de usuários."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.permissoes import PERFIL_VIEWER, PERFIS

SENHA_MINIMA = 8


def _normalizar_login(v: str) -> str:
    """Login é comparado em minúsculas — 'Canaveze' e 'canaveze' são o mesmo."""
    limpo = (v or "").strip().lower()
    if not limpo:
        raise ValueError("Informe o login.")
    return limpo


def _validar_perfil(v: str) -> str:
    perfil = (v or "").strip().lower()
    if perfil not in PERFIS:
        raise ValueError(f"Perfil deve ser um de {list(PERFIS)}.")
    return perfil


class UsuarioCreate(BaseModel):
    """Novo usuário. ``login`` aceita um nome de usuário ou um e-mail."""

    login: str = Field(..., min_length=3, max_length=255)
    nome: str = Field(default="", max_length=255)
    senha: str = Field(..., min_length=SENHA_MINIMA, max_length=128)
    perfil: str = Field(default=PERFIL_VIEWER)
    ativo: bool = True

    _login = field_validator("login")(_normalizar_login)
    _perfil = field_validator("perfil")(_validar_perfil)


class UsuarioUpdate(BaseModel):
    """Alteração de um usuário. Campos ausentes ficam como estão."""

    nome: str | None = Field(default=None, max_length=255)
    perfil: str | None = None
    ativo: bool | None = None

    @field_validator("perfil")
    @classmethod
    def _perfil_valido(cls, v: str | None) -> str | None:
        return None if v is None else _validar_perfil(v)


class SenhaReset(BaseModel):
    """Redefinição de senha feita por um administrador."""

    senha_nova: str = Field(..., min_length=SENHA_MINIMA, max_length=128)


class UsuarioAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login: str
    nome: str
    perfil: str
    ativo: bool

    @classmethod
    def do_modelo(cls, usuario) -> "UsuarioAdminOut":
        # A coluna se chama ``email`` por herança do primeiro desenho, mas o que
        # ela guarda é o identificador de login — que pode ser um nome simples.
        return cls(
            id=usuario.id,
            login=usuario.email,
            nome=usuario.nome,
            perfil=usuario.perfil,
            ativo=usuario.ativo,
        )
