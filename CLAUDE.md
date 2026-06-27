# CLAUDE.md — ERP Multicanal para Marketplace (Mercado Livre + Shopee)

> **Como usar no Claude Code:** salve este arquivo como `CLAUDE.md` na raiz do projeto e abra a pasta no terminal com `claude`. O Claude Code lerá este arquivo automaticamente no início de cada sessão e saberá exatamente o que construir, quais regras seguir e como os dados reais se comportam — sem precisar reexplicar nada.

---

## CONTEXTO DO PROJETO

Estamos construindo um **ERP web multicanal** para um vendedor de autopeças que opera no Mercado Livre e na Shopee. O sistema centraliza cadastros, compras, estoque, pedidos de venda, expedição e financeiro em um único lugar.

**O negócio em números reais (mai–jun 2026):**
- 974 unidades vendidas | R$ 62.412 de receita bruta | **R$ 40.288 líquido recebido**
- Mercado Livre: 678 pedidos, R$ 52.026 bruto → R$ 32.904 líquido
- Shopee: 216 pedidos, R$ 10.386 bruto → R$ 7.384 líquido
- 93% dos envios pelo ML são via Fulfillment (ML Full)

**Produtos:** retentores, anéis de pistão, bronzinas e vedadores de motor automotivo. SKUs numéricos (ex: `5338`, `8126`, `5245`). Cada SKU pode ter múltiplos anúncios/variações no mesmo canal ou entre canais diferentes.

---

## STACK OBRIGATÓRIA

```
Backend:   Python + FastAPI
Banco:     PostgreSQL (integridade referencial é crítica)
Frontend:  React + TypeScript + Tailwind CSS
ORM:       SQLAlchemy (com Alembic para migrations)
Parser:    pandas + openpyxl (leitura das planilhas ML e Shopee)
Auth:      JWT (usuário/perfil)
Testes:    pytest (backend) + Vitest (frontend)
```

**Princípios de código:**
- Nunca hardcode valores calculados — use fórmulas ou queries no banco
- Todas as operações financeiras em `Decimal` (não `float`)
- Toda migration com `alembic revision --autogenerate` antes de qualquer `alembic upgrade head`
- Separar parsers por canal em arquivos distintos: `parsers/mercadolivre.py` e `parsers/shopee.py`
- Testes para toda lógica de cálculo financeiro e de parsing

---

## ESTRUTURA DE DIRETÓRIOS

```
backend/
├── alembic/               ← migrations
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models/            ← um arquivo por entidade
│   │   ├── produto.py
│   │   ├── fornecedor.py
│   │   ├── estoque.py
│   │   ├── pedido.py
│   │   ├── sku_map.py     ← tabela de-para de SKUs
│   │   └── financeiro.py
│   ├── routers/           ← um arquivo por módulo
│   ├── schemas/           ← Pydantic schemas
│   ├── services/          ← lógica de negócio
│   └── parsers/
│       ├── mercadolivre.py
│       └── shopee.py
├── tests/
└── requirements.txt
frontend/
├── src/
│   ├── pages/
│   ├── components/
│   ├── api/               ← cliente HTTP tipado
│   └── types/
└── package.json
```

---

## MÓDULOS A CONSTRUIR (ordem de prioridade)

### PRIORIDADE 1 — Importação de Planilhas e SKU Map
> Sem isso nada funciona. Construir primeiro.

**Parser Mercado Livre** (`parsers/mercadolivre.py`):
- Detectar linha de cabeçalho buscando célula com `"N.º de venda"` (varia entre linha 5–7 dependendo da exportação)
- Ler arquivo com `pd.read_excel(path, header=header_row)`
- Colunas obrigatórias e seus nomes exatos — ver Seção "Mapeamento de Colunas ML" abaixo
- Detectar e tratar pacotes multi-produto — ver Seção "Armadilhas de Parsing"
- Retornar lista de `VendaDTO` com schema unificado

**Parser Shopee** (`parsers/shopee.py`):
- Cabeçalho na linha 1 (sem metadados para pular)
- Calcular `liquido_recebido` = `Subtotal do produto` − `Taxa de comissão líquida` − `Taxa de serviço líquida` − `Taxa de transação` − `Taxa de Envio Reversa`
- Pedidos com `Status do pedido` in `["Cancelado", "Não pago"]` → zerar qtd e valores, `status_erp = "Cancelado"`
- Retornar lista de `VendaDTO` com mesmo schema unificado do ML

**Tela "Mapa de SKUs"** (Prioridade máxima do frontend):
- Lista de `sku_canal` sem mapeamento (pendências)
- Campo de busca para localizar `sku_base` no cadastro de produtos
- Salvar mapeamento na tabela `sku_map`
- Exibir de-para já configurados com opção de editar

### PRIORIDADE 2 — Cadastro de Produtos e Fornecedores
Ver descrição completa no histórico do projeto.

### PRIORIDADE 3 — Estoque Multi-local
### PRIORIDADE 4 — Pedidos de Compra
### PRIORIDADE 5 — Financeiro e Dashboards

---

## MAPEAMENTO DE COLUNAS — MERCADO LIVRE
Arquivo: `Vendas_BR_MercadoLibre_*.xlsx` | Aba: `Vendas BR`

| Campo interno | Coluna ML (nome exato no arquivo) | Tipo |
|---|---|---|
| `id_pedido_canal` | `N.º de venda` | string |
| `data_venda` | `Data da venda` | string → datetime |
| `status_canal` | `Estado` | string |
| `sku_canal` | `SKU` | string (pode estar vazio) |
| `id_anuncio` | `# de anúncio` | string |
| `titulo` | `Título do anúncio` | string |
| `tipo_anuncio` | `Tipo de anúncio` | `Premium` \| `Clássico` |
| `canal_logistico` | `Forma de entrega` | string |
| `qtd` | `Unidades` | decimal (1ª coluna com esse nome) |
| `preco_unitario` | `Preço unitário de venda do anúncio (BRL)` | decimal |
| `receita_bruta` | `Receita por produtos (BRL)` | decimal |
| `tarifa_ml` | `Tarifa de venda e impostos (BRL)` | decimal (negativo) |
| `tarifas_envio` | `Tarifas de envio (BRL)` | decimal (negativo) |
| `receita_envio` | `Receita por envio (BRL)` | decimal (positivo) |
| `descontos` | `Descontos e bônus` | decimal (positivo) |
| `cancelamentos` | `Cancelamentos e reembolsos (BRL)` | decimal (negativo) |
| `liquido_recebido` | `Total (BRL)` | decimal ← **importar direto, não recalcular** |
| `is_pacote_multi` | `Pacote de diversos produtos` | `"Sim"` → True |

**Classificação de status (campo `status_erp`):** ver `parsers/mercadolivre.py`
(`CANCELADOS`, `DEVOLUCOES`).

**Canal logístico:** `Full` → `ML Full`; `Flex` → `ML Flex`; demais → `ML Agência/Correios`.

---

## MAPEAMENTO DE COLUNAS — SHOPEE
Arquivo: `Order_all_*.xlsx` | Aba: `orders` | Cabeçalho na linha 1

| Campo interno | Coluna Shopee (nome exato no arquivo) | Observação |
|---|---|---|
| `id_pedido_canal` | `ID do pedido` | string |
| `data_venda` | `Data de criação do pedido` | formato `AAAA-MM-DD HH:MM` |
| `status_canal` | `Status do pedido` | string |
| `sku_canal` | `Número de referência SKU` | fallback: `Nº de referência do SKU principal` |
| `titulo` | `Nome do Produto` | string |
| `variacao` | `Nome da variação` | string |
| `preco_unitario` | `Preço acordado` | decimal |
| `qtd` | `Quantidade` | decimal → zerar se cancelado |
| `receita_bruta` | `Subtotal do produto` | decimal → zerar se cancelado |
| `comissao` | `Taxa de comissão líquida` | decimal (usar líquida, não bruta) |
| `servico` | `Taxa de serviço líquida` | decimal (usar líquida, não bruta) |
| `transacao` | `Taxa de transação` | decimal |
| `envio_reverso` | `Taxa de Envio Reversa` | decimal |

**Cálculo do líquido (OBRIGATÓRIO — Shopee não entrega o valor pronto):**
ver `parsers/shopee.py::calcular_liquido_shopee`.

---

## ARMADILHAS DE PARSING — CRÍTICO, não pular

1. **Cabeçalho de metadados no ML** (até 5 linhas antes dos dados). Sempre rodar
   `detectar_header_ml()` antes de `pd.read_excel()`. Nunca hardcodar `header=5`.
2. **Pacotes multi-produto no ML** — NUNCA ignorar linhas sem SKU. A linha-resumo
   carrega o dinheiro; as linhas-componente carregam os SKUs para baixa de estoque.
3. **Três colunas `Unidades` no ML** — usar sempre a primeira (`Unidades`).
4. **`Total (BRL)` do ML já é líquido final** — não recalcular.
5. **Shopee: valores de cancelados ainda aparecem preenchidos** — filtrar por
   `Status do pedido` ANTES de somar.
6. **Frete ML — duas colunas distintas:** `Tarifas de envio (BRL)` (custo, negativo)
   e `Receita por envio (BRL)` (frete cobrado, positivo). Frete líquido = soma das duas.

---

## DADOS REAIS DE VALIDAÇÃO (mai–jun 2026)
Após implementar o parser, importar as planilhas reais deve produzir exatamente estes totais:

| Métrica | Mercado Livre | Shopee | Total |
|---|---|---|---|
| Linhas importadas | 678 | 216 | 894 |
| Unidades vendidas | 758 | 216 | 974 |
| Receita bruta (R$) | 52.026,43 | 10.385,88 | 62.412,31 |
| Tarifas plataforma (R$) | −7.901,91 | −3.002,18 | −10.904,09 |
| Frete líquido (R$) | −9.989,47 | 0 | −9.989,47 |
| Descontos/bônus (R$) | +664,15 | 0 | +664,15 |
| Cancelamentos (R$) | −1.894,76 | 0 | −1.894,76 |
| **Líquido recebido (R$)** | **32.904,44** | **7.383,70** | **40.288,14** |

> Use esses números como **assertions nos testes de integração** do parser
> (`tests/test_integration_real.py`). Se a soma não bater, o parsing tem bug.

---

## DE-PARA DE SKUS (seed verificado nos dados reais)
Ver `app/seed/sku_map_seed.py`. ⚠️ `8126STA` (Shopee) é o mesmo produto que
`8126` / `8126STD` / `8126a` (ML) — por isso o de-para manual é obrigatório.

---

## TELAS E ROTAS — REFERÊNCIA RÁPIDA

| Tela | Rota frontend | Endpoint backend |
|---|---|---|
| Importar planilha | `/importar` | `POST /api/importar/ml` e `/api/importar/shopee` |
| Mapa de SKUs | `/sku-map` | `GET/POST /api/sku-map` |

---

## COMANDOS DO PROJETO

```bash
# Backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest -v

# Frontend
cd frontend && npm install && npm run dev && npm run test
```

---

## REGRAS DE COMPORTAMENTO DO CLAUDE CODE NESTE PROJETO
1. Antes de criar qualquer model, verificar/gerar a migration correspondente.
2. Toda função financeira usa `Decimal`, nunca `float`.
3. Parser ML: sempre `detectar_header_ml()` antes de `pd.read_excel()`.
4. Ao importar vendas, resolver `sku_canal → sku_base` via `sku_map`. Sem
   mapeamento → inserir em pendências, não bloquear a importação.
5. Testes de parser devem bater com "Dados Reais de Validação".
6. Nunca apagar vendas importadas sem confirmação. Duplicados detectados por
   `id_pedido_canal + canal` (unique constraint).
7. Todo endpoint de relatório com filtro por período e por canal.
