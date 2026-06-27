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
};
