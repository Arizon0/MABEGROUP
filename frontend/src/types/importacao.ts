export interface TotaisImportacao {
  linhas: number;
  unidades: string;
  receita_bruta: string;
  tarifas_plataforma: string;
  frete_liquido: string;
  descontos: string;
  cancelamentos: string;
  liquido_recebido: string;
}

export interface ResultadoImportacao {
  canal: string;
  linhas_arquivo: number;
  vendas_inseridas: number;
  pedidos_duplicados: number;
  skus_resolvidos: number;
  skus_pendentes: number;
  baixas_estoque: number;
  contas_receber: number;
  cmv_total?: string;
  skus_nao_cadastrados?: string[];
  totais: TotaisImportacao;
}

export interface ResultadoCatalogo {
  linhas: number;
  criados: number;
  atualizados: number;
  ignorados: number;
  erros: string[];
  skus: string[];
}

export interface ResumoLocalEstoque {
  local: string;
  atualizados: number;
  unidades: string;
  valor: string;
}

export interface ResultadoEstoque {
  linhas: number;
  atualizados: number;
  saldos_criados: number;
  ignorados: number;
  unidades_total: string;
  valor_total: string;
  locais: string[];
  por_local: ResumoLocalEstoque[];
  nao_encontrados: string[];
  erros: string[];
}
