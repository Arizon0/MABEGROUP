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
