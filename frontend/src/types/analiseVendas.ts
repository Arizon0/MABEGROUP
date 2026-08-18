/** Tipos da análise venda-a-venda (`/api/vendas/analise`).
 *
 * Todo valor monetário e percentual chega como string: o backend usa `Decimal`
 * e serializa em texto para não perder centavos no `number` do JavaScript.
 * Converta para `Number` só na hora de formatar.
 */

export type Recorte =
  | "todos"
  | "negativos"
  | "sem-custo"
  | "sem-comissao"
  | "sem-frete"
  | "pacotes"
  | "revisar";

export type Ordem =
  | "pior-margem-valor"
  | "pior-margem-pct"
  | "melhor-margem-valor"
  | "melhor-margem-pct"
  | "maior-venda"
  | "maior-frete"
  | "data";

export type Alerta =
  | "sem_sku"
  | "sem_custo"
  | "sem_comissao"
  | "receber_nao_bate";

/** Uma linha da tabela: um pedido, com todos os custos reconstruídos. */
export interface PedidoAnalisado {
  canal: string;
  id_pedido_canal: string;
  numero_nf: string | null;
  data_venda: string | null;
  titulo: string;
  skus: string[];
  anuncios: string[];
  canal_logistico: string;
  status_canal: string;
  linhas: number;
  is_pacote_multi: boolean;
  qtd: string;
  total: string;
  custo: string;
  frete: string;
  comissao: string;
  descontos: string;
  cancelamentos: string;
  liquido_recebido: string;
  ads: string;
  /** Null quando o canal não atribuiu receita à publicidade. */
  acos_pct: string | null;
  tacos_pct: string | null;
  imposto: string;
  aliquota_pct: string;
  margem_valor: string;
  /** Null quando o pedido não tem receita — não existe percentual sem base. */
  margem_pct: string | null;
  diferenca_liquido: string;
  alertas: Alerta[];
}

export interface ResumoAnalise {
  pedidos: number;
  negativos: number;
  pct_negativos: string;
  para_revisar: number;
  unidades: string;
  total: string;
  custo: string;
  frete: string;
  comissao: string;
  ads: string;
  imposto: string;
  liquido_recebido: string;
  margem_valor: string;
  margem_pct: string;
  prejuizo_dos_negativos: string;
  /** Verba de publicidade que não achou pedido para ratear. */
  ads_nao_alocado: string;
}

export interface Paginacao {
  pagina: number;
  tamanho: number;
  total: number;
  paginas: number;
  de: number;
  ate: number;
}

export interface AnaliseVendas {
  filtros: {
    data_inicio: string | null;
    data_fim: string | null;
    canal: string | null;
    recorte: Recorte;
    ordem: Ordem;
    busca: string | null;
  };
  resumo: ResumoAnalise;
  contagem_por_recorte: Record<Recorte, number>;
  paginacao: Paginacao;
  pedidos: PedidoAnalisado[];
}

// Type alias, não interface: só um alias de objeto ganha index signature
// implícita, que é o que permite passar o filtro direto para o montador de
// query string sem espalhar `as Record<...>` pelas chamadas.
export type FiltroAnalise = {
  data_inicio?: string;
  data_fim?: string;
  canal?: string;
  recorte?: Recorte;
  ordem?: Ordem;
  busca?: string;
  pagina?: number;
  tamanho?: number;
};

export interface Aliquota {
  id: number;
  ano: number;
  mes: number;
  aliquota_pct: string;
  observacao: string | null;
}

export interface AliquotaUpsert {
  ano: number;
  mes: number;
  aliquota_pct: string;
  observacao?: string | null;
}

export type EscopoAds = "anuncio" | "sku" | "canal";

export interface Ads {
  id: number;
  canal: string;
  ano: number;
  mes: number;
  escopo: EscopoAds;
  referencia: string;
  valor: string;
  receita_ads: string | null;
}

export interface AdsUpsert {
  canal: string;
  ano: number;
  mes: number;
  escopo: EscopoAds;
  referencia: string;
  valor: string;
  receita_ads?: string | null;
}
