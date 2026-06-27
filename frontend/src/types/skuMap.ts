export type Canal = "Mercado Livre" | "Shopee";

export interface Produto {
  id: number;
  sku_base: string;
  nome: string;
}

export interface SkuMap {
  id: number;
  sku_canal: string;
  canal: Canal;
  id_anuncio: string | null;
  produto_id: number;
  sku_base: string;
  criado_em?: string | null;
}

export interface SkuPendencia {
  id: number;
  sku_canal: string;
  canal: Canal;
  id_anuncio: string | null;
  titulo: string | null;
  ocorrencias: number;
}

export interface SkuMapCreate {
  sku_canal: string;
  canal: Canal;
  id_anuncio?: string | null;
  produto_id?: number | null;
  sku_base?: string | null;
}
