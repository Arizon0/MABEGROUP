import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const navigate = useNavigate();

  async function entrar(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setCarregando(true);
    try {
      await api.login(email, senha);
      navigate("/", { replace: true });
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao entrar");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-6">
      <form
        onSubmit={entrar}
        className="w-full max-w-sm rounded-lg border border-gray-200 bg-white p-8 shadow-sm"
      >
        <h1 className="mb-1 text-2xl font-bold text-gray-900">ERP Multicanal</h1>
        <p className="mb-6 text-sm text-gray-500">Entre com seu usuário e senha.</p>

        {erro && (
          <div className="mb-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
            {erro}
          </div>
        )}

        <label className="mb-3 block text-sm font-medium text-gray-700">
          E-mail
          <input
            type="text"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="input mt-1 w-full"
            placeholder="admin@erp.local"
            required
          />
        </label>

        <label className="mb-6 block text-sm font-medium text-gray-700">
          Senha
          <input
            type="password"
            autoComplete="current-password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            className="input mt-1 w-full"
            placeholder="••••••••"
            required
          />
        </label>

        <button
          type="submit"
          disabled={carregando}
          className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
        >
          {carregando ? "Entrando..." : "Entrar"}
        </button>
      </form>
    </div>
  );
}
