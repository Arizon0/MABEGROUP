"""Configuração da aplicação (lê variáveis de ambiente)."""
from __future__ import annotations

import os

# PostgreSQL em produção; SQLite como padrão de desenvolvimento/teste para
# permitir rodar sem um servidor de banco configurado.
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite:///./erp.db",
)

# Origens permitidas para o frontend (CORS).
CORS_ORIGINS: list[str] = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
).split(",")

# Diretório onde os anexos (até 5 por produto/fornecedor) são gravados.
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")

# --- Autenticação (JWT) -----------------------------------------------------
# IMPORTANTE: em produção defina SECRET_KEY por variável de ambiente.
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-insecure-change-me-please")
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# Usuário administrador criado no seed (e no startup, se ainda não existir).
ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@erp.local")
ADMIN_SENHA: str = os.getenv("ADMIN_SENHA", "admin123")
ADMIN_NOME: str = os.getenv("ADMIN_NOME", "Administrador")
