#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ERP Multicanal — sobe backend (FastAPI) + frontend (React) com um comando.
#
#   ./start.sh
#
# Na primeira execução instala dependências, cria o banco (SQLite), aplica as
# migrations e carrega o seed (locais + de-para de SKUs). Nas próximas, apenas
# sobe os servidores. Ctrl+C encerra os dois.
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Escolhe um Python 3.11+ disponível -------------------------------------
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for c in python3.12 python3.11 python3; do
    command -v "$c" >/dev/null 2>&1 && PY="$c" && break
  done
fi
if [ -z "$PY" ]; then
  echo "✗ Python 3.11+ não encontrado. Instale com:  brew install python@3.11"
  exit 1
fi
echo "→ Python: $($PY --version)"

# --- Backend ----------------------------------------------------------------
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  echo "→ Criando ambiente virtual (.venv)…"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "→ Instalando dependências do backend…"
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "→ Aplicando migrations (cria o banco SQLite na primeira vez)…"
alembic upgrade head

echo "→ Carregando seed (somente se o banco estiver vazio)…"
python - <<'PYEOF'
from app.database import SessionLocal
from app.models.estoque import Local
from app.seed import seed_locais, seed_sku_map

db = SessionLocal()
try:
    if db.query(Local).count() == 0:
        seed_locais(db)
        seed_sku_map(db)
        db.commit()
        print("  ✓ seed aplicado (3 locais + de-para de SKUs + 20 produtos).")
    else:
        print("  • banco já populado — seed ignorado.")
finally:
    db.close()
PYEOF

echo "→ Subindo backend em http://localhost:8000 …"
uvicorn app.main:app --reload --port 8000 &
BACK_PID=$!

cleanup() {
  echo
  echo "Encerrando servidores…"
  kill "$BACK_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- Frontend ---------------------------------------------------------------
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  echo "→ Instalando dependências do frontend (pode demorar na 1ª vez)…"
  npm install
fi

echo ""
echo "============================================================"
echo "  Backend : http://localhost:8000      (API + /docs)"
echo "  Frontend: http://localhost:5173      ← ABRA NO NAVEGADOR"
echo "  Ctrl+C aqui encerra os dois."
echo "============================================================"
echo ""

npm run dev
