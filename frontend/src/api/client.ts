import { encerrarSessao, tokenAtual } from "./sessao";
import type { UsuarioSessao } from "./sessao";
import type {
  Ads,
  AdsUpsert,
  Aliquota,
  AliquotaUpsert,
  AnaliseVendas,
  FiltroAnalise,
} from "../types/analiseVendas";
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
  Dashboard,
  ResumoFinanceiro,
  TipoRelatorio,
} from "../types/dashboard";
import type {
  Local,
  MovimentoIn,
  RelatorioEstoque,
  Saldo,
} from "../types/estoque";
import type {
  Competencia,
  Dre,
  DespesaUpsert,
  Marketplace,
} from "../types/dre";
import type {
  ResultadoCatalogo,
  ResultadoEstoque,
  ResultadoImportacao,
} from "../types/importacao";
import type {
  Produto,
  SkuMap,
  SkuMapCreate,
  SkuPendencia,
} from "../types/skuMap";

export interface FiltroRelatorio {
  data_inicio?: string;
  data_fim?: string;
  canal?: string;
  [key: string]: string | undefined;
}

function qs(params: Record<string, string | number | undefined>): string {
  // `0` e `""` são descartados de propósito: nenhum filtro desta API os usa
  // como valor significativo, e omiti-los mantém a URL curta.
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  if (entries.length === 0) return "";
  return "?" + entries.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");
}

const BASE = import.meta.env.VITE_API_URL ?? "";

export const SESSAO_EXPIRADA = "Sessão expirada. Entre novamente.";

/** Cabeçalhos de autenticação, quando há sessão. */
function autorizacao(): Record<string, string> {
  const token = tokenAtual();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Trata a resposta: 401 encerra a sessão, erro vira exceção legível. */
async function conferir(resp: Response): Promise<Response> {
  if (resp.status === 401) {
    // Descartar o token aqui é o que faz a aplicação voltar para o login
    // sozinha quando o token vence no meio do uso, em vez de encher a tela
    // de erros que o usuário não sabe resolver.
    encerrarSessao();
    throw new Error(SESSAO_EXPIRADA);
  }
  if (!resp.ok) {
    const detail = await resp.text().catch(() => resp.statusText);
    throw new Error(`HTTP ${resp.status}: ${detail}`);
  }
  return resp;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await conferir(
    await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...autorizacao(),
        ...(init?.headers as Record<string, string> | undefined),
      },
    }),
  );
  // DELETE responde 204 sem corpo; `resp.json()` rejeitaria em corpo vazio.
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

async function upload<T>(path: string, arquivo: File): Promise<T> {
  const form = new FormData();
  form.append("arquivo", arquivo);
  // Sem "Content-Type": o navegador precisa montar o boundary do multipart.
  const resp = await conferir(
    await fetch(`${BASE}${path}`, {
      method: "POST",
      body: form,
      headers: autorizacao(),
    }),
  );
  return (await resp.json()) as T;
}

/** Baixa um arquivo protegido e entrega ao navegador.
 *
 * Um `<a href>` comum não serve mais: o navegador não manda o header de
 * autenticação numa navegação, então o download voltaria 401. Aqui a
 * requisição carrega o token, e o resultado vira um link temporário de blob.
 */
export async function baixarArquivo(url: string, nomeArquivo: string): Promise<void> {
  const resp = await conferir(await fetch(url, { headers: autorizacao() }));
  const blob = await resp.blob();
  const endereco = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = endereco;
  link.download = nomeArquivo;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(endereco);
}

export interface RespostaLogin {
  access_token: string;
  token_type: string;
  usuario: UsuarioSessao;
}

export const api = {
  // ---- Autenticação ----
  login: (email: string, senha: string) =>
    request<RespostaLogin>(`/api/auth/login`, {
      method: "POST",
      body: JSON.stringify({ email, senha }),
    }),

  eu: () => request<UsuarioSessao>(`/api/auth/me`),

  trocarSenha: (senha_atual: string, senha_nova: string) =>
    request<RespostaLogin>(`/api/auth/senha`, {
      method: "POST",
      body: JSON.stringify({ senha_atual, senha_nova }),
    }),

  // ---- Importação de planilhas ----
  importarML: (arquivo: File) =>
    upload<ResultadoImportacao>(`/api/importar/ml`, arquivo),

  importarShopee: (arquivo: File) =>
    upload<ResultadoImportacao>(`/api/importar/shopee`, arquivo),

  importarVendasSimples: (arquivo: File) =>
    upload<ResultadoImportacao>(`/api/importar/vendas`, arquivo),

  importarCatalogo: (arquivo: File) =>
    upload<ResultadoCatalogo>(`/api/produtos/importar-catalogo`, arquivo),

  importarEstoque: (arquivo: File) =>
    upload<ResultadoEstoque>(`/api/estoque/importar`, arquivo),

  // ---- DRE ----
  getDre: (ano: number, mes: number, marketplace: Marketplace = "todos") =>
    request<Dre>(
      `/api/dre?ano=${ano}&mes=${mes}&marketplace=${encodeURIComponent(marketplace)}`,
    ),

  getCompetencias: () => request<Competencia[]>(`/api/dre/competencias`),

  salvarDespesaDre: (payload: DespesaUpsert) =>
    request<DespesaUpsert>(`/api/dre/despesas`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  urlExportDre: (
    ano: number,
    mes: number,
    marketplace: Marketplace,
    formato: "excel" | "pdf",
  ) =>
    `${BASE}/api/dre/export?ano=${ano}&mes=${mes}&marketplace=${encodeURIComponent(
      marketplace,
    )}&formato=${formato}`,

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

  // ---- Análise venda-a-venda ----
  getAnaliseVendas: (f: FiltroAnalise = {}) =>
    request<AnaliseVendas>(`/api/vendas/analise${qs(f)}`),

  urlExportAnalise: (formato: "excel" | "pdf", f: FiltroAnalise = {}) =>
    `${BASE}/api/vendas/analise/export${qs({ ...f, pagina: undefined, tamanho: undefined, formato })}`,

  listarAliquotas: () => request<Aliquota[]>(`/api/vendas/aliquotas`),

  salvarAliquota: (payload: AliquotaUpsert) =>
    request<Aliquota>(`/api/vendas/aliquotas`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  excluirAliquota: (id: number) =>
    request<void>(`/api/vendas/aliquotas/${id}`, { method: "DELETE" }),

  listarAds: (ano?: number, mes?: number, canal?: string) =>
    request<Ads[]>(`/api/vendas/ads${qs({ ano, mes, canal })}`),

  salvarAds: (payload: AdsUpsert) =>
    request<Ads>(`/api/vendas/ads`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  excluirAds: (id: number) =>
    request<void>(`/api/vendas/ads/${id}`, { method: "DELETE" }),

  salvarNotaFiscal: (canal: string, id_pedido_canal: string, numero_nf: string | null) =>
    request<unknown>(`/api/vendas/nf`, {
      method: "PUT",
      body: JSON.stringify({ canal, id_pedido_canal, numero_nf }),
    }),

  // ---- Dashboard / Financeiro / Relatórios ----
  getDashboard: (f: FiltroRelatorio = {}) =>
    request<Dashboard>(`/api/dashboard${qs(f)}`),

  getFinanceiro: (f: FiltroRelatorio = {}) =>
    request<ResumoFinanceiro>(`/api/financeiro${qs(f)}`),

  getRelatorio: <T>(tipo: TipoRelatorio, f: FiltroRelatorio = {}) =>
    request<T>(`/api/relatorios/${tipo}${qs(f)}`),

  urlRelatorio: (tipo: TipoRelatorio, formato: "excel" | "pdf", f: FiltroRelatorio = {}) =>
    `${BASE}/api/relatorios/${tipo}${qs({ ...f, formato })}`,
};
