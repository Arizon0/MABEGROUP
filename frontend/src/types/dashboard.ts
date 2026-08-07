export interface ConferenciaMes {
  soma_componentes: string;
  liquido_importado: string;
  diferenca: string;
  confere: boolean;
}

export interface ResumoMes {
  mes: string;
  ano: number;
  mes_num: number;
  pedidos: number;
  produtos_distintos: number;
  unidades: string;
  receita_bruta: string;
  tarifas_plataforma: string;
  frete_liquido: string;
  descontos: string;
  cancelamentos: string;
  liquido_recebido: string;
  cmv: string;
  lucro_bruto: string;
  margem_liquida: string;
  conferencia: ConferenciaMes;
}

export interface Dashboard {
  faturamento_bruto: string;
  liquido_total: string;
  liquido_por_canal: Record<string, string>;
  unidades_vendidas: string;
  qtd_pedidos: number;
  produtos_distintos: number;
  entradas: {
    receita_bruta: string;
    descontos_bonus: string;
  };
  saidas: {
    tarifas_plataforma: string;
    frete_liquido: string;
    cancelamentos: string;
    custo_produtos_vendidos: string;
    custos_operacionais: string;
  };
  custo_produtos_vendidos: string;
  custos_operacionais: string;
  lucro_estimado: string;
  projecoes: Record<string, string>;
  mes_vigente: ResumoMes | null;
  resumo_mensal: ResumoMes[];
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
