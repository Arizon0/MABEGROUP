/** Sessão do usuário: token JWT e identidade, guardados no navegador.
 *
 * O token fica em `localStorage` para sobreviver a recarregar a página e a
 * fechar a aba. Isso o deixa legível por JavaScript da própria origem — o que
 * é aceitável aqui porque a API é stateless por Bearer token (não usa cookie
 * de sessão) e não há conteúdo de terceiros injetado nas telas.
 */

export interface UsuarioSessao {
  id: number;
  email: string;
  nome: string;
  perfil: string;
}

const CHAVE_TOKEN = "erp.token";
const CHAVE_USUARIO = "erp.usuario";

type Ouvinte = () => void;
const ouvintes = new Set<Ouvinte>();

/** `localStorage` lança em modo privado de alguns navegadores — nunca deixe
 *  a leitura derrubar a aplicação inteira. */
function ler(chave: string): string | null {
  try {
    return localStorage.getItem(chave);
  } catch {
    return null;
  }
}

function gravar(chave: string, valor: string | null): void {
  try {
    if (valor === null) localStorage.removeItem(chave);
    else localStorage.setItem(chave, valor);
  } catch {
    /* sessão só na memória desta aba */
  }
}

export function tokenAtual(): string | null {
  return ler(CHAVE_TOKEN);
}

export function usuarioAtual(): UsuarioSessao | null {
  const bruto = ler(CHAVE_USUARIO);
  if (!bruto) return null;
  try {
    return JSON.parse(bruto) as UsuarioSessao;
  } catch {
    return null;
  }
}

export function guardarSessao(token: string, usuario: UsuarioSessao): void {
  gravar(CHAVE_TOKEN, token);
  gravar(CHAVE_USUARIO, JSON.stringify(usuario));
  notificar();
}

export function encerrarSessao(): void {
  gravar(CHAVE_TOKEN, null);
  gravar(CHAVE_USUARIO, null);
  notificar();
}

/** Avisa a aplicação quando a sessão muda — inclusive quando a API devolve 401
 *  e o token é descartado no meio de uma requisição. */
export function observarSessao(ouvinte: Ouvinte): () => void {
  ouvintes.add(ouvinte);
  return () => ouvintes.delete(ouvinte);
}

function notificar(): void {
  ouvintes.forEach((o) => o());
}
