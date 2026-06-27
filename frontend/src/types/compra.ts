export type StatusPedido = "rascunho" | "aprovado" | "recebido" | "cancelado";

export interface ItemCompra {
  id: number;
  produto_id: number;
  qtd: string;
  custo_unitario: string;
  subtotal: string;
}

export interface PedidoCompra {
  id: number;
  fornecedor_id: number;
  local_id?: number | null;
  status: StatusPedido;
  observacao?: string | null;
  criado_em?: string | null;
  aprovado_em?: string | null;
  recebido_em?: string | null;
  total: string;
  itens: ItemCompra[];
}

export interface ItemCompraIn {
  produto_id: number;
  qtd: string;
  custo_unitario: string;
}

export interface PedidoCompraCreate {
  fornecedor_id: number;
  itens: ItemCompraIn[];
  observacao?: string | null;
}

export interface SugestaoCompra {
  produto_id: number;
  sku_base: string;
  nome: string;
  media_mensal: string;
  estoque_minimo: string;
  qtd_pendente: string;
  qtd_atual: string;
  qtd_sugerida: string;
  repor: boolean;
}
