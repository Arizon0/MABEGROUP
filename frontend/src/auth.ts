// Gerenciamento simples do token JWT no navegador (localStorage).
const TOKEN_KEY = "erp_token";
const USER_KEY = "erp_user";

export interface AuthUser {
  id: number;
  email: string;
  nome: string;
  perfil: string;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function setSession(token: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

/** Limpa a sessão e manda para a tela de login (em caso de 401). */
export function logout(): void {
  clearSession();
  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}
