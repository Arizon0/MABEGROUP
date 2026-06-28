# Deploy no Vercel — ERP Multicanal

Dois projetos no Vercel (ambos a partir do mesmo repositório) + o banco Supabase
que você já criou (`erp-db`).

- **Backend** (FastAPI) → projeto Vercel com _Root Directory_ = `backend`
- **Frontend** (React/Vite) → projeto Vercel com _Root Directory_ = `frontend`

O backend lê a URL do banco automaticamente (`POSTGRES_URL`, injetada pela
integração Supabase) e tem CORS aberto, então não há configuração de URL cruzada.

---

## 1. Backend

1. No Vercel: **Add New → Project** → importe `Arizon0/MABEGROUP`.
2. **Root Directory** = **`backend`**.
3. **Storage**: conecte o banco `erp-db` a este projeto (isso injeta `POSTGRES_URL`).
4. **Environment Variables**:

   | Nome | Valor |
   |---|---|
   | `SECRET_KEY` | chave aleatória longa (protege o login) |
   | `SETUP_TOKEN` | um segredo só seu (usado uma vez, no passo 2) |
   | `ADMIN_EMAIL` | seu e-mail de login |
   | `ADMIN_SENHA` | a senha que você vai usar |

5. **Deploy**. Anote a URL (ex.: `https://erp-backend.vercel.app`).

## 2. Inicializar o banco (uma vez, pelo navegador)

Abra no navegador, trocando pela sua URL e seu `SETUP_TOKEN`:

```
https://SEU-BACKEND.vercel.app/api/admin/setup?token=SEU_SETUP_TOKEN
```

Deve aparecer um JSON com `"schema": "ok"` e as contagens do seed (admin, locais,
de-para). Isso cria as tabelas, ativa o RLS (tranca a API pública do Supabase) e
cria seu usuário. É idempotente — pode abrir de novo sem problema.

## 3. Frontend

1. **Add New → Project** → mesmo repositório.
2. **Root Directory** = **`frontend`** (o Vercel detecta Vite sozinho).
3. **Environment Variables**:

   | Nome | Valor |
   |---|---|
   | `VITE_API_URL` | a URL do backend do passo 1 |

4. **Deploy**. Anote a URL (ex.: `https://erp.vercel.app`).

## 4. Pronto

Acesse a URL do frontend e faça login com `ADMIN_EMAIL` / `ADMIN_SENHA`.

---

### Observações
- **Anexos** (arquivos de produto/fornecedor) não persistem no Vercel (disco
  somente-leitura); precisariam de storage externo (ex.: Vercel Blob).
- A primeira chamada após inatividade pode demorar alguns segundos (cold start
  do Python por causa do pandas).
- Depois do passo 2 você pode remover `SETUP_TOKEN` para desativar o endpoint.

### Gerar uma SECRET_KEY
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
