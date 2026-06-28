import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Produto, ProdutoCreate } from "../types/cadastro";

const FORM_VAZIO: ProdutoCreate = {
  sku_base: "",
  nome: "",
  categoria: "",
  unidade_medida: "UN",
  estoque_minimo: "0",
  preco_compra: "",
  preco_venda: "",
};

export function ProdutosPage() {
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [busca, setBusca] = useState("");
  const [form, setForm] = useState<ProdutoCreate>(FORM_VAZIO);
  const [mostrarForm, setMostrarForm] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  const recarregar = useCallback(async (q?: string) => {
    setCarregando(true);
    try {
      setProdutos(await api.listarProdutosCadastro(q));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar produtos");
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void recarregar();
  }, [recarregar]);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    try {
      const payload: ProdutoCreate = {
        ...form,
        preco_compra: form.preco_compra || null,
        preco_venda: form.preco_venda || null,
      };
      await api.criarProduto(payload);
      setForm(FORM_VAZIO);
      setMostrarForm(false);
      await recarregar(busca);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar produto");
    }
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Produtos</h1>
          <p className="text-sm text-gray-500">Cadastro de produtos e variantes.</p>
        </div>
        <button
          type="button"
          onClick={() => setMostrarForm((v) => !v)}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {mostrarForm ? "Cancelar" : "+ Novo produto"}
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
          className="mb-6 grid grid-cols-1 gap-3 rounded border border-gray-200 bg-white p-4 sm:grid-cols-3"
        >
          <Campo label="SKU base *">
            <input
              required
              value={form.sku_base}
              onChange={(e) => setForm({ ...form, sku_base: e.target.value })}
              className="input"
            />
          </Campo>
          <Campo label="Nome *" className="sm:col-span-2">
            <input
              required
              value={form.nome}
              onChange={(e) => setForm({ ...form, nome: e.target.value })}
              className="input"
            />
          </Campo>
          <Campo label="Categoria">
            <input
              value={form.categoria ?? ""}
              onChange={(e) => setForm({ ...form, categoria: e.target.value })}
              className="input"
            />
          </Campo>
          <Campo label="Unidade">
            <input
              value={form.unidade_medida ?? "UN"}
              onChange={(e) => setForm({ ...form, unidade_medida: e.target.value })}
              className="input"
            />
          </Campo>
          <Campo label="Estoque mínimo">
            <input
              value={form.estoque_minimo ?? "0"}
              onChange={(e) => setForm({ ...form, estoque_minimo: e.target.value })}
              className="input"
            />
          </Campo>
          <Campo label="Preço compra (R$)">
            <input
              value={form.preco_compra ?? ""}
              onChange={(e) => setForm({ ...form, preco_compra: e.target.value })}
              className="input"
            />
          </Campo>
          <Campo label="Preço venda (R$)">
            <input
              value={form.preco_venda ?? ""}
              onChange={(e) => setForm({ ...form, preco_venda: e.target.value })}
              className="input"
            />
          </Campo>
          <div className="flex items-end">
            <button
              type="submit"
              className="rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
            >
              Salvar
            </button>
          </div>
        </form>
      )}

      <div className="mb-3">
        <input
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && recarregar(busca)}
          placeholder="Buscar por SKU ou nome (Enter)..."
          className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
        />
      </div>

      {carregando ? (
        <p className="text-gray-500">Carregando...</p>
      ) : produtos.length === 0 ? (
        <p className="text-sm text-gray-500">Nenhum produto cadastrado.</p>
      ) : (
        <div className="overflow-hidden rounded border border-gray-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-3 py-2">SKU base</th>
                <th className="px-3 py-2">Nome</th>
                <th className="px-3 py-2">Categoria</th>
                <th className="px-3 py-2 text-right">Preço venda</th>
                <th className="px-3 py-2 text-center">Variantes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {produtos.map((p) => (
                <tr key={p.id} className="hover:bg-gray-50">
                  <td className="px-3 py-2 font-mono font-semibold">{p.sku_base}</td>
                  <td className="px-3 py-2">{p.nome}</td>
                  <td className="px-3 py-2 text-gray-600">{p.categoria ?? "—"}</td>
                  <td className="px-3 py-2 text-right">
                    {p.preco_venda ? `R$ ${p.preco_venda}` : "—"}
                  </td>
                  <td className="px-3 py-2 text-center text-gray-500">
                    {p.variantes?.length ?? 0}
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
