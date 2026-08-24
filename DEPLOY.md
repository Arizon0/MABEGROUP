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
> de-para) carregado no start — e que **some quando o contêiner é recriado**.
>
> Para guardar os dados em disco, mande o banco para uma pasta própria e monte
> só ela. Não monte um volume em `/app/backend`: é onde o código da aplicação
> mora, e o volume o esconderia (`ModuleNotFoundError: No module named 'app'`).
> ```bash
> docker run -p 8000:8000 \
>   -e DATABASE_URL="sqlite:////dados/erp.db" \
>   -e UPLOAD_DIR="/dados/uploads" \
>   -v "$PWD/dados:/dados" mabegroup
> ```
>
> Ou aponte para um Postgres:
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


---

## Segurança — leia antes de expor na internet

A API **exige autenticação em todo endpoint** de dados. Sem um
`Authorization: Bearer <token>` válido, tudo responde 401. Só três rotas são
públicas, cada uma por um motivo:

| Rota | Por que é pública |
|---|---|
| `GET /health` | sonda do orquestrador, que precisa responder antes de haver sessão |
| `POST /api/auth/login` | é onde o token nasce |
| `/api/admin/setup` | bootstrap, travado pelo próprio `SETUP_TOKEN` |

A trava é declarada **no registro dos routers** (`main.py`), não endpoint a
endpoint — um endpoint novo entra protegido por padrão. O teste
`tests/test_seguranca.py::TestTrava::test_todo_endpoint_de_api_exige_token`
varre todas as rotas registradas e cobra 401 de cada uma, então desproteger
algo por descuido quebra a suíte.

### Variáveis que você precisa definir

| Variável | Obrigatória | O que acontece se ficar no padrão |
|---|---|---|
| `SECRET_KEY` | **sim, em produção** | **a aplicação se recusa a subir.** O valor de exemplo está publicado neste repositório: com ele, qualquer pessoa assina um token de administrador válido |
| `ADMIN_SENHA` | recomendada | sobe, mas registra aviso no log. Troque em **Minha conta** no primeiro acesso |
| `CORS_ORIGINS` | recomendada | `*`. Aceitável porque a autenticação é por Bearer (não por cookie), mas restringir ao seu domínio é melhor |
| `DATABASE_URL` | **sim, em produção** | SQLite dentro do contêiner, que some a cada deploy |

Gere uma `SECRET_KEY` assim:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

O `render.yaml` já resolve isso sozinho: `SECRET_KEY` e `ADMIN_SENHA` usam
`generateValue: true`, então nascem aleatórias e nunca passam pelo Git. Depois
do primeiro deploy, leia a senha em **Environment** no painel do serviço, entre
uma vez e troque em **Minha conta**.

### Usuários e perfis

Três perfis, verificados **no servidor**:

| Perfil | Pode |
|---|---|
| `viewer` | só consulta. Qualquer método que altere dados responde 403 |
| `analista` | opera o sistema: importa, edita, lança, exclui. Não vê nem mexe em usuários |
| `admin` | tudo, incluindo o cadastro de usuários |

O bloqueio do `viewer` é por **método HTTP**, aplicado no registro dos routers:
um endpoint de escrita novo já nasce fechado para ele, sem ninguém precisar
lembrar de anotá-lo.

O cadastro fica em **Usuários** (visível só para admin). O item some do menu
para os outros perfis, mas isso é conveniência: quem chamar `/api/usuarios`
direto leva 403 do mesmo jeito.

**Ninguém se tranca do lado de fora.** O sistema recusa qualquer operação que
deixaria zero administradores ativos — inclusive um admin rebaixando a si
mesmo. Quando há outro admin ativo, a operação é liberada (um sócio pode sair).
Admin desativado não conta como substituto. Excluir a própria conta logada é
sempre recusado; para sair, desative ou rebaixe.

### Contas de proprietário no primeiro boot

Para um deploy novo já subir com os donos podendo entrar, defina:

| Variável | Exemplo |
|---|---|
| `USUARIOS_INICIAIS` | `arizono,Canaveze` |
| `SENHA_INICIAL` | a senha que os dois vão usar no primeiro acesso |

As contas nascem com perfil `admin`. O seed é idempotente e **nunca reescreve a
senha de um login que já existe** — se alguém já trocou a dele, rodar o seed de
novo não desfaz isso.

Sem `SENHA_INICIAL` definida, nenhuma conta é criada e o log avisa o motivo. É
proposital: uma senha embutida no código entraria no histórico do Git e
continuaria pública mesmo depois de trocada no sistema.

Depois do primeiro acesso, apague ou desative a conta genérica
`admin@erp.local` em **Usuários** — ela existe só para o bootstrap.

### O que ainda não existe

- **Limite de tentativas de login.** Nada impede um atacante de testar senhas em
  série. Com senha forte o risco é baixo, mas se o sistema for ficar exposto por
  muito tempo, vale colocar rate limit.
- **Registro de auditoria.** Não fica gravado quem importou, editou ou excluiu o
  quê. Com poucas pessoas de confiança isso não pesa; com uma equipe maior, sim.
- **Recuperação de senha por e-mail.** Quem esquecer depende de um admin usar o
  botão "Redefinir senha" na tela de Usuários.
