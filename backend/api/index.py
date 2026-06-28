"""Ponto de entrada serverless do Vercel.

O Vercel detecta o app ASGI exportado aqui e serve o FastAPI inteiro. Todas as
rotas (/api/..., /health) são encaminhadas para este app pelo vercel.json.
"""
from app.main import app  # noqa: F401  (exportado para o runtime do Vercel)
