export interface Dashboard {
  faturamento_bruto: string;
  liquido_total: string;
  liquido_por_canal: Record<string, string>;
  unidades_vendidas: string;
  custo_produtos_vendidos: string;
  custos_operacionais: string;
  lucro_estimado: string;
  projecoes: Record<string, string>;
}

export interface ResumoConta {
  total: string;
  aberto: string;
  liquidado: string;
  quantidade: number;
}

export interface ResumoFinanceiro {
  a_pagar: ResumoConta;
  a_receber: ResumoConta;
  saldo_projetado: string;
}

export interface DRE {
  receita_bruta: string;
  tarifas_plataforma: string;
  frete_liquido: string;
  descontos: string;
  cancelamentos: string;
  liquido_recebido: string;
  custo_produtos_vendidos: string;
  margem_bruta: string;
}

export interface RankingReceita {
  sku_base: string;
  unidades: string;
  liquido: string;
}

export type TipoRelatorio = "dre" | "ranking" | "giro" | "fluxo-caixa";
