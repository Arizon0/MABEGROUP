import type {
  Fornecedor,
  FornecedorCreate,
  Produto as ProdutoCompleto,
  ProdutoCreate,
} from "../types/cadastro";
import type {
  PedidoCompra,
  PedidoCompraCreate,
  SugestaoCompra,
} from "../types/compra";
import type {
  Local,
  MovimentoIn,
  RelatorioEstoque,
  Saldo,
} from "../types/estoque";
import type {
  Produto,
  SkuMap,
  SkuMapCreate,
  SkuPendencia,
} from "../types/skuMap";

const BASE = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    const detail = await resp.text().catch(() => resp.statusText);
    throw new Error(`HTTP ${resp.status}: ${detail}`);
  }
  return (await resp.json()) as T;
}

export const api = {
  // ---- SKU Map ----
  listarSkuMap: (canal?: string) =>
    request<SkuMap[]>(`/api/sku-map${canal ? `?canal=${encodeURIComponent(canal)}` : ""}`),

  listarPendencias: (canal?: string) =>
    request<SkuPendencia[]>(
      `/api/sku-map/pendencias${canal ? `?canal=${encodeURIComponent(canal)}` : ""}`,
    ),

  buscarProdutos: (q: string) =>
    request<Produto[]>(`/api/sku-map/produtos?q=${encodeURIComponent(q)}`),

  salvarSkuMap: (payload: SkuMapCreate) =>
    request<SkuMap>(`/api/sku-map`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // ---- Produtos ----
  listarProdutosCadastro: (q?: string) =>
    request<ProdutoCompleto[]>(
      `/api/produtos${q ? `?q=${encodeURIComponent(q)}` : ""}`,
    ),

  obterProduto: (id: number) => request<ProdutoCompleto>(`/api/produtos/${id}`),

  criarProduto: (payload: ProdutoCreate) =>
    request<ProdutoCompleto>(`/api/produtos`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // ---- Fornecedores ----
  listarFornecedores: (q?: string) =>
    request<Fornecedor[]>(
      `/api/fornecedores${q ? `?q=${encodeURIComponent(q)}` : ""}`,
    ),

  criarFornecedor: (payload: FornecedorCreate) =>
    request<Fornecedor>(`/api/fornecedores`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // ---- Estoque ----
  listarSaldos: (q?: string) =>
    request<Saldo[]>(`/api/estoque${q ? `?q=${encodeURIComponent(q)}` : ""}`),

  listarLocais: () => request<Local[]>(`/api/estoque/locais`),

  relatorioEstoque: () => request<RelatorioEstoque>(`/api/estoque/relatorio`),

  registrarMovimento: (payload: MovimentoIn) =>
    request<unknown>(`/api/estoque/movimentos`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // ---- Compras ----
  listarCompras: (status?: string) =>
    request<PedidoCompra[]>(
      `/api/compras${status ? `?status=${encodeURIComponent(status)}` : ""}`,
    ),

  sugestaoCompra: () => request<SugestaoCompra[]>(`/api/compras/sugestao`),

  criarCompra: (payload: PedidoCompraCreate) =>
    request<PedidoCompra>(`/api/compras`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  aprovarCompra: (id: number) =>
    request<PedidoCompra>(`/api/compras/${id}/aprovar`, { method: "POST" }),

  receberCompra: (id: number) =>
    request<PedidoCompra>(`/api/compras/${id}/receber`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
};
