# Deploy no Vercel — ERP Multicanal

O sistema tem duas partes, cada uma vira **um projeto no Vercel** (ambos no
Vercel, conforme combinado):

- **Backend** (FastAPI) → projeto Vercel com _Root Directory_ = `backend`
- **Frontend** (React/Vite) → projeto Vercel com _Root Directory_ = `frontend`

E um **banco Postgres** na nuvem (o SQLite não funciona no Vercel).

---

## 1. Criar o banco Postgres (grátis)

No painel do Vercel: **Storage → Create Database → Postgres (Neon)**. Dê um nome
(ex.: `erp-db`) e crie. Copie a **connection string** (`DATABASE_URL`), algo como:

```
postgres://usuario:senha@host.neon.tech/neondb?sslmode=require
```

> Guarde essa string — ela é usada no backend e para criar as tabelas.

## 2. Deploy do BACKEND

1. **Add New → Project** → importe o repositório `Arizon0/MABEGROUP`.
2. Em **Root Directory**, selecione **`backend`**.
3. Em **Environment Variables**, adicione:

   | Nome | Valor |
   |---|---|
   | `DATABASE_URL` | a connection string do passo 1 |
   | `SECRET_KEY` | uma chave aleatória longa (ver abaixo) |
   | `ADMIN_EMAIL` | seu e-mail de login (ex.: `voce@empresa.com`) |
   | `ADMIN_SENHA` | a senha que você vai usar |
   | `CORS_ORIGINS` | preencher depois do passo 4 com a URL do frontend |

4. **Deploy**. Ao final, anote a URL do backend (ex.: `https://erp-backend.vercel.app`).

## 3. Criar as tabelas e o usuário admin

As tabelas precisam ser criadas uma vez no Postgres. **Me passe a `DATABASE_URL`**
que eu rodo as migrations + o seed (admin, locais, de-para) daqui — ou rode você:

```bash
cd backend
DATABASE_URL="<sua connection string>" alembic upgrade head
DATABASE_URL="<sua connection string>" ADMIN_EMAIL="voce@empresa.com" ADMIN_SENHA="suasenha" \
  python -c "from app.database import SessionLocal; from app.seed import seed_admin, seed_locais, seed_sku_map; db=SessionLocal(); seed_admin(db); seed_locais(db); seed_sku_map(db); db.close(); print('ok')"
```

## 4. Deploy do FRONTEND

1. **Add New → Project** → mesmo repositório.
2. Em **Root Directory**, selecione **`frontend`** (o Vercel detecta Vite sozinho).
3. Em **Environment Variables**, adicione:

   | Nome | Valor |
   |---|---|
   | `VITE_API_URL` | a URL do backend do passo 2 (ex.: `https://erp-backend.vercel.app`) |

4. **Deploy**. Anote a URL do frontend (ex.: `https://erp.vercel.app`).

## 5. Liberar o CORS

Volte ao **projeto do backend → Settings → Environment Variables** e ajuste
`CORS_ORIGINS` com a URL do frontend (passo 4). Faça **Redeploy** do backend.

---

## Pronto

Acesse a URL do frontend, faça login com `ADMIN_EMAIL` / `ADMIN_SENHA` e o
sistema está no ar. Para carregar suas vendas, use a importação de planilhas
(quando a tela de Importar estiver disponível) ou o endpoint
`POST /api/importar/ml` e `/shopee`.

### Observações
- **Anexos** (arquivos de produto/fornecedor) não persistem no Vercel (disco
  somente-leitura). Precisariam de um storage externo (ex.: Vercel Blob/S3).
- A primeira chamada após inatividade pode demorar alguns segundos (cold start
  do Python, por causa do pandas).

### Gerar uma SECRET_KEY
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
