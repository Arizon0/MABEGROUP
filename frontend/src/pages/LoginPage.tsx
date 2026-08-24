import { useState } from "react";
import { api } from "../api/client";
import { guardarSessao } from "../api/sessao";

/** Tela de entrada. Enquanto não houver sessão, é a única coisa renderizada. */
export function LoginPage() {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [entrando, setEntrando] = useState(false);

  async function entrar(evento: React.FormEvent) {
    evento.preventDefault();
    setEntrando(true);
    setErro(null);
    try {
      const resposta = await api.login(email.trim(), senha);
      guardarSessao(resposta.access_token, resposta.usuario);
    } catch (e) {
      // A API não diz se o erro foi o e-mail ou a senha, de propósito: isso
      // deixaria descobrir quais e-mails existem no sistema.
      const bruto = e instanceof Error ? e.message : "";
      setErro(
        bruto.includes("401")
          ? "E-mail ou senha incorretos."
          : "Não foi possível entrar. Verifique sua conexão e tente de novo.",
      );
    } finally {
      setEntrando(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <form
        onSubmit={entrar}
        className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h1 className="text-xl font-bold tracking-tight text-slate-900">ERP Multicanal</h1>
        <p className="mt-1 mb-6 text-sm text-slate-500">Entre para acessar o sistema.</p>

        <label className="mb-4 block text-sm font-medium text-slate-700">
          E-mail
          <input
            type="email"
            autoComplete="username"
            required
            className="input mt-1 block w-full"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>

        <label className="mb-6 block text-sm font-medium text-slate-700">
          Senha
          <input
            type="password"
            autoComplete="current-password"
            required
            className="input mt-1 block w-full"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />
        </label>

        {erro && (
          <p role="alert" className="mb-4 rounded bg-red-50 px-3 py-2 text-sm text-red-700">
            {erro}
          </p>
        )}

        <button
          type="submit"
          disabled={entrando}
          className="w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {entrando ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </div>
  );
}
