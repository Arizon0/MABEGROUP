export type Marketplace = "todos" | "Mercado Livre" | "Shopee";

export interface Competencia {
  ano: number;
  mes: number;
}

export interface GrupoDespesa {
  itens: Record<string, string>;
  total: string;
}

export interface Dre {
  competencia: Competencia;
  marketplace: string;
  unidades: string;
  receitas: {
    mercado_livre: string;
    shopee: string;
    receita_bruta: string;
    deducoes: GrupoDespesa;
    receita_liquida: string;
  };
  cmv: string;
  lucro_bruto: string;
  despesas_operacionais: {
    mercado_livre: GrupoDespesa;
    shopee: GrupoDespesa;
    total: string;
  };
  lucro_operacional: string;
  despesas_gerais: GrupoDespesa;
  lucro_liquido: string;
  ebitda: string;
  margens: {
    bruta: string;
    operacional: string;
    liquida: string;
  };
}

// grupo -> { categoria: valor }
export type DespesasAgrupadas = Record<string, Record<string, string>>;

export interface DespesaUpsert {
  ano: number;
  mes: number;
  grupo: string;
  categoria: string;
  valor: string;
}
