# MABEGROUP — ERP Multicanal (Mercado Livre + Shopee)

ERP web multicanal para um vendedor de autopeças que opera no Mercado Livre e na
Shopee. Veja [`CLAUDE.md`](./CLAUDE.md) para o contexto completo, regras de
negócio e mapeamento das planilhas.

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
