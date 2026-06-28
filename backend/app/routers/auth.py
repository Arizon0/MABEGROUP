"""Endpoints de autenticação: login e usuário atual."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest, TokenOut, UsuarioOut
from app.services.auth import autenticar, criar_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenOut:
    """Valida e-mail/senha e devolve um token JWT."""
    usuario = autenticar(db, payload.email, payload.senha)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
        )
    return TokenOut(
        access_token=criar_access_token(usuario),
        usuario=UsuarioOut.model_validate(usuario),
    )


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(get_current_user)) -> UsuarioOut:
    """Devolve os dados do usuário autenticado (valida o token)."""
    return UsuarioOut.model_validate(usuario)
