"""Autenticação: hash de senha (bcrypt), tokens JWT e dependência de usuário."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    SECRET_KEY,
)
from app.database import get_db
from app.models.usuario import Usuario

# tokenUrl é usado apenas pela UI do /docs; o token é extraído do header.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_BCRYPT_MAX = 72  # bcrypt ignora bytes além de 72; truncamos para evitar erro.


def hash_senha(senha: str) -> str:
    """Gera o hash bcrypt da senha."""
    raw = senha.encode("utf-8")[:_BCRYPT_MAX]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    """Confere a senha contra o hash armazenado."""
    try:
        raw = senha.encode("utf-8")[:_BCRYPT_MAX]
        return bcrypt.checkpw(raw, senha_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def criar_access_token(usuario: Usuario) -> str:
    """Cria um JWT assinado com o id do usuário no campo ``sub``."""
    expira = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(usuario.id),
        "email": usuario.email,
        "perfil": usuario.perfil,
        "exp": expira,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def autenticar(db: Session, email: str, senha: str) -> Optional[Usuario]:
    """Retorna o usuário se e-mail/senha conferem e a conta está ativa."""
    usuario = db.execute(
        select(Usuario).where(Usuario.email == email.strip().lower())
    ).scalar_one_or_none()
    if usuario is None or not usuario.ativo:
        return None
    if not verificar_senha(senha, usuario.senha_hash):
        return None
    return usuario


_CRED_INVALIDA = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais inválidas ou sessão expirada",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """Dependência: valida o JWT do header e devolve o usuário autenticado."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub", ""))
    except (jwt.PyJWTError, ValueError):
        raise _CRED_INVALIDA
    usuario = db.get(Usuario, user_id)
    if usuario is None or not usuario.ativo:
        raise _CRED_INVALIDA
    return usuario
