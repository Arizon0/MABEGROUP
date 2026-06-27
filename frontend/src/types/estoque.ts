export interface Local {
  id: number;
  nome: string;
  tipo: string;
  ativo: boolean;
}

export interface Saldo {
  produto_id: number;
  sku_base: string;
  nome_produto: string;
  local_id: number;
  local_nome: string;
  qtd_disponivel: string;
  qtd_reservada: string;
  custo_medio: string;
  valor_total: string;
}

export interface Alerta {
  produto_id: number;
  sku_base: string;
  nome: string;
  disponivel_total: string;
  estoque_minimo: string;
}

export interface RankingItem {
  sku_base: string | null;
  unidades: string;
  liquido: string;
}

export interface RelatorioEstoque {
  valor_total_estoque: string;
  total_alertas: number;
  alertas: Alerta[];
  ranking_skus: RankingItem[];
}

export type TipoMovimento = "entrada" | "saida" | "reserva" | "liberacao";

export interface MovimentoIn {
  produto_id: number;
  local_id: number;
  tipo: TipoMovimento;
  qtd: string;
  custo_unitario?: string | null;
  referencia?: string | null;
}
