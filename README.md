# MABEGROUP — ERP Multicanal (Mercado Livre + Shopee)

ERP web multicanal para um vendedor de autopeças que opera no Mercado Livre e na
Shopee. Veja [`CLAUDE.md`](./CLAUDE.md) para o contexto completo, regras de
negócio e mapeamento das planilhas.

## 🚀 Colocar no ar (sem Vercel)

Um clique — publica de graça no Render (lê `render.yaml` + `Dockerfile`):

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Arizon0/MABEGROUP/tree/claude/dre-marketplace-system-gt0x9u)

Ou rode na sua máquina com Docker (2 comandos → http://localhost:8000):

```bash
docker build -t mabegroup .
docker run -p 8000:8000 mabegroup
```

Login inicial: `admin@erp.local` / `admin123`. Detalhes em [`DEPLOY.md`](./DEPLOY.md).

## Status — Prioridade 1 (Importação de Planilhas + SKU Map)

Implementado nesta etapa:

- **Parser Mercado Livre** (`backend/app/parsers/mercadolivre.py`): detecção
  automática do cabeçalho, pacotes multi-produto (resumo + componentes), três
  colunas `Unidades`, `Total (BRL)` importado direto, frete líquido.
- **Parser Shopee** (`backend/app/parsers/shopee.py`): cálculo do líquido,
  zeragem de cancelados/não pagos, fallback de SKU.
- **Schema unificado** `VendaDTO` + agregação de totais (`services/totais.py`).
- **SKU Map**: models (`sku_map`, `sku_pendencias`), resolução com registro de
  pendências (não bloqueia a importação), seed do de-para verificado.
- **API**: `POST /api/importar/ml`, `POST /api/importar/shopee`,
  `GET/POST /api/sku-map`, `GET /api/sku-map/pendencias`, `GET /api/sku-map/produtos`.
- **Frontend**: tela **Mapa de SKUs** (React + TS + Tailwind) com pendências,
  busca de produto e de-para configurados.
- **Migrations** Alembic (schema inicial) e **testes** (pytest + Vitest),
  incluindo teste de integração contra as planilhas reais (skip se ausentes).

## Status — Prioridade 2 (Cadastro de Produtos e Fornecedores)

- **Produto** (`backend/app/models/produto.py`): cadastro completo — categoria/
  subcategoria, atributos livres (JSON), medidas/peso, fiscais (NCM + alíquotas
  ICMS/PIS/COFINS/IPI), estoque mínimo/segurança, preços, fornecedor padrão e
  **variantes** (auto-relacionamento produto-pai → variantes).
- **Fornecedor** (`backend/app/models/fornecedor.py`): CNPJ com **validação de
  dígito verificador** (`services/validators.py`), endereço completo, N contatos,
  condições de pagamento e prazo de entrega.
- **Anexos** (`backend/app/models/anexo.py`): até **5 por produto/fornecedor**
  (limite na camada de serviço), gravados em `UPLOAD_DIR`.
- **API**: `GET/POST/PUT /api/produtos` (+ `/{id}/anexos`),
  `GET/POST/PUT /api/fornecedores` (+ `/{id}/anexos`).
- **Frontend**: telas **Produtos** e **Fornecedores** (lista + formulário de
  cadastro, contatos dinâmicos, CNPJ formatado).
- **Migration** Alembic `767897…` (segura em tabela já populada via
  `server_default`).

## Status — Prioridade 3 (Estoque Multi-local)

- **Models** (`backend/app/models/estoque.py`): `Local` (galpão, fulfillment,
  escritório), `EstoqueSaldo` (produto × local: disponível, reservado, custo
  médio) e `MovimentoEstoque` (razão/ledger de toda movimentação).
- **Serviço** (`backend/app/services/estoque.py`): entrada com **custo médio
  ponderado**, saída (com bloqueio por estoque insuficiente), **reserva/
  liberação**, alertas (`disponível <= estoque_mínimo`), valor total do estoque
  e ranking de SKUs mais vendidos.
- **Integração com vendas**: a importação baixa o estoque das vendas válidas no
  local do canal logístico (**ML Full → ML Fulfillment**, demais → galpão).
- **API**: `GET /api/estoque` (saldo SKU × local), `/api/estoque/locais`,
  `/api/estoque/alertas`, `/api/estoque/relatorio`, `POST /api/estoque/movimentos`.
- **Frontend**: tela **Estoque** com valor total, alertas, ranking e saldos.
- **Migration** Alembic `d11591…` (novas tabelas) e seed dos locais padrão.

> Testes: backend **56 passed / 3 skipped**, frontend **6 passed**.

## Status — Prioridade 4 (Pedidos de Compra)

- **Models** (`backend/app/models/compra.py`, `financeiro.py`): `PedidoCompra`
  + `ItemPedidoCompra` (fluxo rascunho → aprovado → recebido) e `ContaPagar`.
- **Serviço** (`backend/app/services/compras.py`):
  - criar pedido (rascunho), **aprovar** (gera lançamento em `contas_a_pagar`
    com vencimento = hoje + prazo do fornecedor),
  - **receber** (incrementa estoque com custo médio ponderado),
  - **sugestão automática** de quantidade a repor por SKU:
    `media_mensal + estoque_mínimo + qtd_pendente − qtd_atual` (repor quando > 0).
- **API**: `GET/POST /api/compras`, `/api/compras/sugestao`,
  `POST /api/compras/{id}/aprovar`, `/receber`, `/anexos` (NF de entrada).
- **Frontend**: tela **Compras** com sugestão de reposição (destaque em vermelho),
  formulário de pedido e ações aprovar/receber.
- **Migration** Alembic `88a346…` (novas tabelas).

> Testes: backend **64 passed / 3 skipped**, frontend **8 passed**.

## Status — Prioridade 5 (Financeiro e Dashboards)

- **Contas a receber** (`backend/app/models/financeiro.py`): lançadas
  automaticamente a cada importação de venda (a pagar já vinha da aprovação de
  compra).
- **Dashboard** (`GET /api/dashboard`): faturamento bruto, líquido por canal,
  lucro estimado (líquido − CMV − custos operacionais) e projeções 15/30/60/90
  dias (média móvel).
- **Financeiro** (`GET /api/financeiro` + `/contas-pagar`, `/contas-receber`):
  resumo de contas a pagar/receber e saldo projetado, com filtro de período/canal.
- **Relatórios** (`GET /api/relatorios/{tipo}`): **DRE** simplificado, **ranking**
  de SKUs por receita líquida, **giro** de estoque e **fluxo de caixa** mensal —
  todos com filtro de período + canal e exportáveis em **Excel e PDF**.
- **Frontend**: telas **Dashboard** (home), **Financeiro** e **Relatórios** (com
  filtros e download Excel/PDF).
- **Migration** Alembic `5433…` (contas_a_receber).

> Testes: backend **80 passed / 3 skipped**, frontend **9 passed**.

---

## Status — Análise de Vendas (margem real por pedido)

Tela `/analise-vendas`: a margem de **cada pedido**, com os custos que as
planilhas do canal não entregam reconstruídos.

- **Serviço** (`backend/app/services/vendas_analise.py`): consolida as linhas
  importadas em pedidos (pacote multi-produto vira 1 pedido), aplica imposto e
  rateia publicidade. `margem = líquido − CMV − Ads − Imposto`.
- **Imposto** (`aliquotas_imposto`): alíquota efetiva **com vigência** por
  competência — cadastrar agosto não reescreve o imposto já apurado em maio.
- **Publicidade** (`ads_investimento`): investimento do mês rateado proporcional
  à receita, no escopo mais específico que casar (anúncio → SKU → canal).
  **ACOS** usa a receita que o canal atribuiu a Ads (mostra `—` sem ela);
  **TACOS** usa a receita total.
- **Recortes**: todos · só negativos · sem custo · sem comissão · sem frete ·
  vários pacotes · a receber não bate. Cada chip mostra quantos pedidos esconde.
- **Ordenações**: pior/melhor margem em R$ e em %, maior venda, maior frete, data.
- **Qualidade do dado**: alertas por pedido (`sem_sku`, `sem_custo`,
  `sem_comissao`, `receber_nao_bate`) e aviso quando sobra verba de Ads sem ratear.
- **Nota fiscal**: lida do export do ML quando existe, editável na própria linha.
- **Endpoints**: `GET /api/vendas/analise`, `/analise/opcoes`, `/analise/export`
  (Excel/PDF), CRUD de `/aliquotas` e `/ads`, `PUT /nf`.
- **Migration** Alembic `b7c1e2f30a44`.

> Testes: backend **186 passed / 3 skipped**, frontend **32 passed**.

---

## Status — Autenticação (pré-requisito para publicar)

A infraestrutura de login existia (bcrypt, JWT, `get_current_user`), mas **não
estava conectada**: o router de auth nunca foi registrado e nenhum endpoint
exigia token. A API inteira respondia sem credencial. Esta entrega ligou tudo.

- **Trava no registro dos routers** (`main.py`): a exigência de token é
  declarada no `include_router`, não endpoint a endpoint — endpoint novo entra
  protegido por padrão. Públicas apenas `/health`, `/api/auth/login` e
  `/api/admin/setup` (esta com o próprio `SETUP_TOKEN`).
- **Varredura de regressão**: `test_todo_endpoint_de_api_exige_token` percorre
  todas as rotas registradas e cobra 401 de cada uma.
- **Boot defensivo**: em produção, `SECRET_KEY` no valor de exemplo **derruba o
  boot** — esse valor é público neste repositório e permitiria a qualquer pessoa
  assinar um token de administrador. Senha do admin no padrão vira aviso no log.
- **Frontend**: tela de login, sessão em `localStorage`, token em toda
  requisição (inclusive no upload de planilha), e 401 no meio do uso volta para
  o login sozinho.
- **Downloads**: os botões de Excel/PDF deixaram de ser `<a href>` — o navegador
  não manda o header de autenticação numa navegação, então baixam via fetch
  autenticado e blob.
- **Troca de senha** em "Minha conta", exigindo a senha atual.
- **`render.yaml`**: `SECRET_KEY` e `ADMIN_SENHA` com `generateValue`, CORS
  restrito ao domínio do serviço.

> Testes: backend **267 passed / 3 skipped**, frontend **59 passed**.

---

## Status — Usuários e perfis de acesso

- **Três perfis** (`viewer`, `analista`, `admin`) verificados no servidor. O
  bloqueio do perfil de leitura é por **método HTTP**, declarado no registro dos
  routers — endpoint de escrita novo já nasce fechado para ele.
- **Tela Usuários** (só admin): criar, trocar perfil, ativar/desativar,
  redefinir senha e excluir. O item some do menu para os outros perfis, mas a
  recusa de verdade é o 403 do servidor.
- **Ninguém se tranca do lado de fora**: o sistema recusa qualquer operação que
  zeraria os administradores ativos, inclusive um admin rebaixando a si mesmo.
  Com outro admin ativo, é liberado — um sócio pode sair. Admin desativado não
  conta como substituto.
- **Contas de proprietário no primeiro boot** via `USUARIOS_INICIAIS` e
  `SENHA_INICIAL`. Idempotente e nunca reescreve senha já trocada. Sem a senha
  no ambiente, não cria conta alguma — em vez de embutir uma no repositório.
- **Login aceita nome de usuário**, não só e-mail.

> Testes: backend **311 passed / 3 skipped**, frontend **75 passed**.

---

### Roadmap concluído

Prioridades 1 → 5 implementadas (parsers + SKU Map, cadastros, estoque,
compras, financeiro/dashboards). **36 endpoints** REST, **5 migrations** Alembic,
**8 telas** React. Os 3 testes "skipped" rodam automaticamente quando as
planilhas reais são disponibilizadas, validando os totais oficiais.

## Como rodar

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head            # cria o schema (DATABASE_URL ou SQLite padrão)
uvicorn app.main:app --reload   # http://localhost:8000
pytest -v                       # testes
```

Para validar contra as planilhas reais, aponte-as por variável de ambiente
(ou coloque em `backend/tests/data/`):
```bash
ERP_ML_XLSX=/caminho/Vendas_BR_MercadoLibre_*.xlsx \
ERP_SHOPEE_XLSX=/caminho/Order_all_*.xlsx \
pytest tests/test_integration_real.py -v
```

### Frontend
```bash
cd frontend
npm install
npm run dev       # http://localhost:5173 (proxy /api -> :8000)
npm run test      # Vitest
```
