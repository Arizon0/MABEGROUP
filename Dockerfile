# ERP/DRE Multicanal — imagem única (backend FastAPI serve o frontend Vite).
# Roda em qualquer lugar: `docker build -t mabegroup . && docker run -p 8000:8000 mabegroup`
# Sobe em http://localhost:8000 (UI + API na mesma origem).

# ---------- Stage 1: build do frontend ----------
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# VITE_API_URL vazio => o frontend chama a API na MESMA origem (/api/...)
RUN VITE_API_URL="" npm run build

# ---------- Stage 2: runtime Python ----------
FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    INIT_DB=1 \
    STATIC_DIR=/app/frontend/dist

# Dependências de runtime (sem pandas: os parsers usam openpyxl) + servidor.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt "uvicorn[standard]==0.34.0"

# Código do backend e o frontend já compilado.
COPY backend/ /app/backend/
COPY --from=frontend /app/frontend/dist /app/frontend/dist

WORKDIR /app/backend
EXPOSE 8000

# PORT é injetado por Render/Railway/Fly; cai para 8000 localmente.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
