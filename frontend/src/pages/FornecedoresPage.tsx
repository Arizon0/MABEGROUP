import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Contato, Fornecedor, FornecedorCreate } from "../types/cadastro";

const FORM_VAZIO: FornecedorCreate = {
  cnpj: "",
  razao_social: "",
  nome_fantasia: "",
  uf: "",
  cidade: "",
  condicoes_pagamento_dias: undefined,
  prazo_medio_entrega_dias: undefined,
  contatos: [],
};

export function FornecedoresPage() {
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);
  const [busca, setBusca] = useState("");
  const [form, setForm] = useState<FornecedorCreate>(FORM_VAZIO);
  const [contatos, setContatos] = useState<Contato[]>([]);
  const [mostrarForm, setMostrarForm] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  const recarregar = useCallback(async (q?: string) => {
    setCarregando(true);
    try {
      setFornecedores(await api.listarFornecedores(q));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar fornecedores");
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void recarregar();
  }, [recarregar]);

  function addContato() {
    setContatos([...contatos, { nome: "", cargo: "", email: "" }]);
  }
  function setContato(i: number, patch: Partial<Contato>) {
    setContatos(contatos.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));
  }
  function removeContato(i: number) {
    setContatos(contatos.filter((_, idx) => idx !== i));
  }

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    try {
      await api.criarFornecedor({
        ...form,
        condicoes_pagamento_dias: form.condicoes_pagamento_dias || null,
        prazo_medio_entrega_dias: form.prazo_medio_entrega_dias || null,
        contatos: contatos.filter((c) => c.nome.trim()),
      });
      setForm(FORM_VAZIO);
      setContatos([]);
      setMostrarForm(false);
      await recarregar(busca);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar fornecedor");
    }
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Fornecedores</h1>
          <p className="text-sm text-gray-500">Cadastro com CNPJ validado e contatos.</p>
        </div>
        <button
          type="button"
          onClick={() => setMostrarForm((v) => !v)}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {mostrarForm ? "Cancelar" : "+ Novo fornecedor"}
        </button>
      </header>

      {erro && (
        <div className="mb-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {erro}
        </div>
      )}

      {mostrarForm && (
        <form
          onSubmit={salvar}
          className="mb-6 space-y-3 rounded border border-gray-200 bg-white p-4"
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Campo label="CNPJ *">
              <input
                required
                value={form.cnpj}
                onChange={(e) => setForm({ ...form, cnpj: e.target.value })}
                placeholder="00.000.000/0000-00"
                className="input"
              />
            </Campo>
            <Campo label="Razão social *" className="sm:col-span-2">
              <input
                required
                value={form.razao_social}
                onChange={(e) => setForm({ ...form, razao_social: e.target.value })}
                className="input"
              />
            </Campo>
            <Campo label="Nome fantasia">
              <input
                value={form.nome_fantasia ?? ""}
                onChange={(e) => setForm({ ...form, nome_fantasia: e.target.value })}
                className="input"
              />
            </Campo>
            <Campo label="Cidade">
              <input
                value={form.cidade ?? ""}
                onChange={(e) => setForm({ ...form, cidade: e.target.value })}
                className="input"
              />
            </Campo>
            <Campo label="UF">
              <input
                maxLength={2}
                value={form.uf ?? ""}
                onChange={(e) => setForm({ ...form, uf: e.target.value.toUpperCase() })}
                className="input"
              />
            </Campo>
            <Campo label="Cond. pagamento (dias)">
              <input
                type="number"
                value={form.condicoes_pagamento_dias ?? ""}
                onChange={(e) =>
                  setForm({ ...form, condicoes_pagamento_dias: Number(e.target.value) || undefined })
                }
                className="input"
              />
            </Campo>
            <Campo label="Prazo entrega (dias)">
              <input
                type="number"
                value={form.prazo_medio_entrega_dias ?? ""}
                onChange={(e) =>
                  setForm({ ...form, prazo_medio_entrega_dias: Number(e.target.value) || undefined })
                }
                className="input"
              />
            </Campo>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-semibold uppercase text-gray-500">Contatos</span>
              <button
                type="button"
                onClick={addContato}
                className="text-sm font-medium text-blue-600 hover:underline"
              >
                + Adicionar contato
              </button>
            </div>
            {contatos.map((c, i) => (
              <div key={i} className="mb-2 grid grid-cols-1 gap-2 sm:grid-cols-4">
                <input
                  placeholder="Nome"
                  value={c.nome}
                  onChange={(e) => setContato(i, { nome: e.target.value })}
                  className="input"
                />
                <input
                  placeholder="Cargo"
                  value={c.cargo ?? ""}
                  onChange={(e) => setContato(i, { cargo: e.target.value })}
                  className="input"
                />
                <input
                  placeholder="E-mail"
                  value={c.email ?? ""}
                  onChange={(e) => setContato(i, { email: e.target.value })}
                  className="input"
                />
                <button
                  type="button"
                  onClick={() => removeContato(i)}
                  className="text-sm text-red-600 hover:underline"
                >
                  Remover
                </button>
              </div>
            ))}
          </div>

          <button
            type="submit"
            className="rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
          >
            Salvar fornecedor
          </button>
        </form>
      )}

      <div className="mb-3">
        <input
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && recarregar(busca)}
          placeholder="Buscar por razão social, fantasia ou CNPJ (Enter)..."
          className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
        />
      </div>

      {carregando ? (
        <p className="text-gray-500">Carregando...</p>
      ) : fornecedores.length === 0 ? (
        <p className="text-sm text-gray-500">Nenhum fornecedor cadastrado.</p>
      ) : (
        <div className="overflow-hidden rounded border border-gray-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-3 py-2">CNPJ</th>
                <th className="px-3 py-2">Razão social</th>
                <th className="px-3 py-2">Cidade/UF</th>
                <th className="px-3 py-2 text-center">Contatos</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {fornecedores.map((f) => (
                <tr key={f.id} className="hover:bg-gray-50">
                  <td className="px-3 py-2 font-mono">{formatarCnpj(f.cnpj)}</td>
                  <td className="px-3 py-2">
                    {f.razao_social}
                    {f.nome_fantasia ? (
                      <span className="text-gray-400"> · {f.nome_fantasia}</span>
                    ) : null}
                  </td>
                  <td className="px-3 py-2 text-gray-600">
                    {[f.cidade, f.uf].filter(Boolean).join("/") || "—"}
                  </td>
                  <td className="px-3 py-2 text-center text-gray-500">
                    {f.contatos?.length ?? 0}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function formatarCnpj(cnpj: string): string {
  const n = cnpj.replace(/\D/g, "");
  if (n.length !== 14) return cnpj;
  return `${n.slice(0, 2)}.${n.slice(2, 5)}.${n.slice(5, 8)}/${n.slice(8, 12)}-${n.slice(12)}`;
}

function Campo({
  label,
  children,
  className = "",
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={`flex flex-col gap-1 text-xs font-medium text-gray-600 ${className}`}>
      {label}
      {children}
    </label>
  );
}
