# Deploy — ERP/DRE Multicanal (serviço único, sem Vercel)

O app roda como **um único serviço**: o backend FastAPI serve a API **e** o
frontend React já compilado, na mesma porta/origem. Isso torna o deploy trivial
em qualquer lugar que rode um contêiner Docker.

---

## Opção 1 — Rodar localmente com Docker (1 comando)

```bash
docker build -t mabegroup .
docker run -p 8000:8000 mabegroup
```

Acesse **http://localhost:8000** — Dashboard, DRE, Produtos, Importação, tudo
na mesma URL. Login inicial: `admin@erp.local` / `admin123`.

> Banco: por padrão SQLite dentro do contêiner, com o seed (35 produtos +
> de-para) carregado no start. Para dados persistentes, aponte `DATABASE_URL`
> para um Postgres:
> ```bash
> docker run -p 8000:8000 -e DATABASE_URL="postgresql://user:senha@host:5432/db" mabegroup
> ```

---

## Opção 2 — Publicar de graça no Render (URL pública, via GitHub)

1. Este repositório já está no GitHub.
2. Acesse **https://dashboard.render.com** → **New** → **Blueprint**.
3. Conecte o repositório `Arizon0/MABEGROUP` (branch da sua escolha).
4. O Render lê o `render.yaml`, builda o `Dockerfile` e publica em
   `https://mabegroup-dre.onrender.com` (o nome pode variar).

Pronto — sem Vercel, sem configurar frontend/backend separados.

**Dados persistentes (opcional):** no Render, crie um **PostgreSQL** (plano
free), copie a *Internal Database URL* e defina `DATABASE_URL` nas variáveis de
ambiente do serviço web. A aplicação detecta Postgres e migra o schema sozinha.

---

## Opção 3 — Railway / Fly.io / qualquer host com Docker

Todos leem o `Dockerfile` da raiz. No Railway: **New Project → Deploy from
GitHub repo** (ele detecta o Dockerfile). No Fly: `fly launch` (usa o
Dockerfile). Exponha a porta `8000` (ou use a variável `PORT`, já suportada).

---

## Variáveis de ambiente

| Nome | Uso | Padrão |
|---|---|---|
| `PORT` | porta do servidor (injetada pelo host) | `8000` |
| `INIT_DB` | cria schema + seed no start (`1` = sim) | `1` no Docker |
| `DATABASE_URL` | Postgres para dados persistentes | SQLite local |
| `SECRET_KEY` | assina o login (JWT) | gere uma no deploy |
| `ADMIN_EMAIL` / `ADMIN_SENHA` | usuário admin inicial | `admin@erp.local` / `admin123` |

---

## Desenvolvimento local (sem Docker)

```bash
# Backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt uvicorn[standard]
INIT_DB=1 uvicorn app.main:app --reload --port 8000

# Frontend (dev com hot-reload, chamando a API em :8000)
cd frontend && npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

Para servir tudo por um processo só (como em produção), compile o frontend com
`VITE_API_URL="" npm run build` e suba apenas o backend com
`STATIC_DIR=../frontend/dist`.
