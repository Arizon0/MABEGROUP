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
