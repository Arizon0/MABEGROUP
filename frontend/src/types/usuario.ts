/** Tipos do cadastro de usuários e perfis de acesso. */

export type Perfil = "viewer" | "analista" | "admin";

export interface Usuario {
  id: number;
  /** Identificador de entrada: um nome de usuário ou um e-mail. */
  login: string;
  nome: string;
  perfil: Perfil;
  ativo: boolean;
}

export interface UsuarioCreate {
  login: string;
  nome?: string;
  senha: string;
  perfil: Perfil;
  ativo?: boolean;
}

export interface UsuarioUpdate {
  nome?: string;
  perfil?: Perfil;
  ativo?: boolean;
}

/** O que cada perfil pode fazer, para explicar a escolha na tela. */
export const DESCRICAO_PERFIL: Record<Perfil, string> = {
  viewer: "Só consulta. Não importa planilha, não edita, não exclui.",
  analista: "Opera o sistema: importa, edita e lança. Não mexe em usuários.",
  admin: "Acesso total, incluindo o cadastro de usuários.",
};

export const PERFIS: Perfil[] = ["viewer", "analista", "admin"];
