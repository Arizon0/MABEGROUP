import { useState } from "react";
import { api } from "../api/client";
import { guardarSessao, usuarioAtual } from "../api/sessao";

/** Conta do usuário: identidade e troca de senha.
 *
 * Existe porque o primeiro acesso usa uma senha de exemplo definida no deploy —
 * sem uma forma de trocá-la pela própria aplicação, ela ficaria valendo para
 * sempre.
 */
export function ContaPage() {
  const usuario = usuarioAtual();
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [salvando, setSalvando] = useState(false);

  async function trocar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    setOk(false);

    if (nova !== confirmacao) {
      setErro("A confirmação não confere com a senha nova.");
      return;
    }
    if (nova.length < 8) {
      setErro("A senha nova precisa ter ao menos 8 caracteres.");
      return;
    }

    setSalvando(true);
    try {
      // A API devolve um token novo: o antigo continuaria válido até vencer,
      // e renovar aqui deixa a sessão coerente com a senha recém-definida.
      const resposta = await api.trocarSenha(atual, nova);
      guardarSessao(resposta.access_token, resposta.usuario);
      setAtual("");
      setNova("");
      setConfirmacao("");
      setOk(true);
    } catch (e) {
      const bruto = e instanceof Error ? e.message : "";
      setErro(bruto.includes("400") ? "Senha atual incorreta." : "Não foi possível trocar a senha.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg p-4 sm:p-6">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900">Minha conta</h1>

      <dl className="my-6 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-slate-500">Nome</dt>
        <dd className="text-slate-900">{usuario?.nome || "—"}</dd>
        <dt className="text-slate-500">E-mail</dt>
        <dd className="text-slate-900">{usuario?.email || "—"}</dd>
        <dt className="text-slate-500">Perfil</dt>
        <dd className="text-slate-900">{usuario?.perfil || "—"}</dd>
      </dl>

      <form onSubmit={trocar} className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-4 text-sm font-semibold text-slate-900">Trocar senha</h2>

        <label className="mb-3 block text-sm text-slate-700">
          Senha atual
          <input
            type="password"
            autoComplete="current-password"
            required
            className="input mt-1 block w-full"
            value={atual}
            onChange={(e) => setAtual(e.target.value)}
          />
        </label>
        <label className="mb-3 block text-sm text-slate-700">
          Senha nova
          <input
            type="password"
            autoComplete="new-password"
            required
            className="input mt-1 block w-full"
            value={nova}
            onChange={(e) => setNova(e.target.value)}
          />
        </label>
        <label className="mb-4 block text-sm text-slate-700">
          Confirme a senha nova
          <input
            type="password"
            autoComplete="new-password"
            required
            className="input mt-1 block w-full"
            value={confirmacao}
            onChange={(e) => setConfirmacao(e.target.value)}
          />
        </label>

        {erro && (
          <p role="alert" className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">
            {erro}
          </p>
        )}
        {ok && (
          <p role="status" className="mb-3 rounded bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            Senha trocada.
          </p>
        )}

        <button
          type="submit"
          disabled={salvando}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {salvando ? "Salvando…" : "Trocar senha"}
        </button>
      </form>
    </div>
  );
}
