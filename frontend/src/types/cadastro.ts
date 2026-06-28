export interface Variante {
  id: number;
  sku_base: string;
  nome: string;
  preco_venda?: string | null;
}

export interface Produto {
  id: number;
  sku_base: string;
  nome: string;
  descricao?: string | null;
  categoria?: string | null;
  subcategoria?: string | null;
  atributos?: Record<string, unknown> | null;
  unidade_medida: string;
  peso_kg?: string | null;
  ncm?: string | null;
  aliquota_icms?: string | null;
  estoque_minimo: string;
  estoque_seguranca: string;
  preco_compra?: string | null;
  preco_venda?: string | null;
  fornecedor_padrao_id?: number | null;
  produto_pai_id?: number | null;
  variantes: Variante[];
}

export interface ProdutoCreate {
  sku_base: string;
  nome: string;
  categoria?: string | null;
  subcategoria?: string | null;
  unidade_medida?: string;
  ncm?: string | null;
  estoque_minimo?: string;
  preco_compra?: string | null;
  preco_venda?: string | null;
  fornecedor_padrao_id?: number | null;
}

export interface Contato {
  id?: number;
  nome: string;
  cargo?: string | null;
  telefone?: string | null;
  email?: string | null;
}

export interface Fornecedor {
  id: number;
  cnpj: string;
  razao_social: string;
  nome_fantasia?: string | null;
  inscricao_estadual?: string | null;
  cidade?: string | null;
  uf?: string | null;
  condicoes_pagamento_dias?: number | null;
  prazo_medio_entrega_dias?: number | null;
  contatos: Contato[];
}

export interface FornecedorCreate {
  cnpj: string;
  razao_social: string;
  nome_fantasia?: string | null;
  uf?: string | null;
  cidade?: string | null;
  condicoes_pagamento_dias?: number | null;
  prazo_medio_entrega_dias?: number | null;
  contatos?: Contato[];
}
