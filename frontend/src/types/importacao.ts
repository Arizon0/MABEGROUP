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
  totais: TotaisImportacao;
}
