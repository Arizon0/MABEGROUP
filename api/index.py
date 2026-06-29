"""Entrypoint serverless do Vercel (projeto único na raiz do repositório).

O código do backend vive em /backend; adicionamos ao sys.path e importamos o
app FastAPI. O vercel.json inclui backend/app/** no bundle da função
(includeFiles) e encaminha /api/* para cá.
"""
import os
import sys

_BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.main import app  # noqa: E402,F401  (exportado para o runtime do Vercel)
