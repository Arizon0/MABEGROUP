"""Configuração da aplicação (lê variáveis de ambiente)."""
from __future__ import annotations

import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _normalizar_db_url(url: str) -> str:
    """Ajusta a URL do banco para o SQLAlchemy/psycopg2.

    - "postgres://" -> "postgresql://" (exigência do SQLAlchemy 2.x).
    - Remove o parâmetro "supa" do pooler do Supabase, que o libpq rejeita.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    partes = urlsplit(url)
    if partes.query:
        filtrados = [
            (k, v)
            for k, v in parse_qsl(partes.query, keep_blank_values=True)
            if k != "supa"
        ]
        url = urlunsplit(
            (partes.scheme, partes.netloc, partes.path, urlencode(filtrados), partes.fragment)
        )
    return url


# PostgreSQL em produção; SQLite como padrão de desenvolvimento/teste para
# permitir rodar sem um servidor de banco configurado.
# A integração Supabase↔Vercel injeta a URL como POSTGRES_URL — lemos os dois.
DATABASE_URL: str = _normalizar_db_url(
    os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or "sqlite:///./erp.db"
)

# Origens permitidas para o frontend (CORS). Padrão "*" porque a autenticação é
# por Bearer token (header), não por cookie — então não precisamos de credentials
# e o backend fica agnóstico à URL do frontend (evita reconfigurar a cada deploy).
CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")

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

# Token do endpoint de inicialização (POST /api/admin/setup). Vazio = desativado.
SETUP_TOKEN: str = os.getenv("SETUP_TOKEN", "")
