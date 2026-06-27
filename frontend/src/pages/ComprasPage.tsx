import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Fornecedor, Produto } from "../types/cadastro";
import type {
  ItemCompraIn,
  PedidoCompra,
  StatusPedido,
  SugestaoCompra,
} from "../types/compra";

const STATUS_CORES: Record<StatusPedido, string> = {
  rascunho: "bg-gray-100 text-gray-700",
  aprovado: "bg-blue-100 text-blue-700",
  recebido: "bg-green-100 text-green-700",
  cancelado: "bg-red-100 text-red-700",
};

const ITEM_VAZIO: ItemCompraIn = { produto_id: 0, qtd: "1", custo_unitario: "0" };

export function ComprasPage() {
  const [pedidos, setPedidos] = useState<PedidoCompra[]>([]);
  const [sugestoes, setSugestoes] = useState<SugestaoCompra[]>([]);
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  const [fornecedorId, setFornecedorId] = useState<number>(0);
  const [itens, setItens] = useState<ItemCompraIn[]>([{ ...ITEM_VAZIO }]);
  const [mostrarForm, setMostrarForm] = useState(false);

  const recarregar = useCallback(async () => {
    setCarregando(true);
    setErro(null);
    try {
      const [p, s, f, prods] = await Promise.all([
        api.listarCompras(),
        api.sugestaoCompra(),
        api.listarFornecedores(),
        api.listarProdutosCadastro(),
      ]);
      setPedidos(p);
      setSugestoes(s);
      setFornecedores(f);
      setProdutos(prods);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar compras");
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void recarregar();
  }, [recarregar]);

  async function acao(fn: () => Promise<unknown>) {
    setErro(null);
    try {
      await fn();
      await recarregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro na operação");
    }
  }

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (!fornecedorId) {
      setErro("Selecione um fornecedor");
      return;
    }
    const validos = itens.filter((i) => i.produto_id > 0 && Number(i.qtd) > 0);
    if (validos.length === 0) {
      setErro("Adicione ao menos um item");
      return;
    }
    await acao(async () => {
      await api.criarCompra({ fornecedor_id: fornecedorId, itens: validos });
      setFornecedorId(0);
      setItens([{ ...ITEM_VAZIO }]);
      setMostrarForm(false);
    });
  }

  function setItem(i: number, patch: Partial<ItemCompraIn>) {
    setItens(itens.map((it, idx) => (idx === i ? { ...it, ...patch } : it)));
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Pedidos de Compra</h1>
          <p className="text-sm text-gray-500">
            Rascunho → Aprovado → Recebido, com sugestão automática de reposição.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setMostrarForm((v) => !v)}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {mostrarForm ? "Cancelar" : "+ Novo pedido"}
        </button>
      </header>

      {erro && (
        <div className="mb-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {erro}
        </div>
      )}

      {mostrarForm && (
        <form onSubmit={salvar} className="mb-6 space-y-3 rounded border border-gray-200 bg-white p-4">
          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            Fornecedor *
            <select
              value={fornecedorId}
              onChange={(e) => setFornecedorId(Number(e.target.value))}
              className="input"
            >
              <option value={0}>Selecione...</option>
              {fornecedores.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.razao_social}
                </option>
              ))}
            </select>
          </label>

          <div className="space-y-2">
            {itens.map((item, i) => (
              <div key={i} className="grid grid-cols-1 gap-2 sm:grid-cols-4">
                <select
                  value={item.produto_id}
                  onChange={(e) => setItem(i, { produto_id: Number(e.target.value) })}
                  className="input sm:col-span-2"
                >
                  <option value={0}>Produto...</option>
                  {produtos.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.sku_base} — {p.nome}
                    </option>
                  ))}
                </select>
                <input
                  placeholder="Qtd"
                  value={item.qtd}
                  onChange={(e) => setItem(i, { qtd: e.target.value })}
                  className="input"
                />
                <input
                  placeholder="Custo unit."
                  value={item.custo_unitario}
                  onChange={(e) => setItem(i, { custo_unitario: e.target.value })}
                  className="input"
                />
              </div>
            ))}
            <button
              type="button"
              onClick={() => setItens([...itens, { ...ITEM_VAZIO }])}
              className="text-sm font-medium text-blue-600 hover:underline"
            >
              + Adicionar item
            </button>
          </div>

          <button
            type="submit"
            className="rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
          >
            Salvar rascunho
          </button>
        </form>
      )}

      {carregando ? (
        <p className="text-gray-500">Carregando...</p>
      ) : (
        <>
          <section className="mb-8">
            <h2 className="mb-3 text-lg font-semibold text-gray-800">Sugestão de compra</h2>
            {sugestoes.length === 0 ? (
              <p className="text-sm text-gray-500">Sem dados para sugerir reposição.</p>
            ) : (
              <div className="overflow-hidden rounded border border-gray-200">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
                    <tr>
                      <th className="px-3 py-2">SKU</th>
                      <th className="px-3 py-2">Produto</th>
                      <th className="px-3 py-2 text-right">Média/mês</th>
                      <th className="px-3 py-2 text-right">Mínimo</th>
                      <th className="px-3 py-2 text-right">Atual</th>
                      <th className="px-3 py-2 text-right">Sugerido</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {sugestoes.map((s) => (
                      <tr key={s.produto_id} className="hover:bg-gray-50">
                        <td className="px-3 py-2 font-mono font-semibold">{s.sku_base}</td>
                        <td className="px-3 py-2">{s.nome}</td>
                        <td className="px-3 py-2 text-right text-gray-600">{s.media_mensal}</td>
                        <td className="px-3 py-2 text-right text-gray-600">{s.estoque_minimo}</td>
                        <td className="px-3 py-2 text-right text-gray-600">{s.qtd_atual}</td>
                        <td
                          className={`px-3 py-2 text-right font-bold ${
                            s.repor ? "text-red-600" : "text-green-600"
                          }`}
                        >
                          {s.qtd_sugerida}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-gray-800">
              Pedidos ({pedidos.length})
            </h2>
            {pedidos.length === 0 ? (
              <p className="text-sm text-gray-500">Nenhum pedido de compra.</p>
            ) : (
              <div className="overflow-hidden rounded border border-gray-200">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
                    <tr>
                      <th className="px-3 py-2">#</th>
                      <th className="px-3 py-2">Status</th>
                      <th className="px-3 py-2 text-center">Itens</th>
                      <th className="px-3 py-2 text-right">Total</th>
                      <th className="px-3 py-2 text-right">Ações</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {pedidos.map((p) => (
                      <tr key={p.id} className="hover:bg-gray-50">
                        <td className="px-3 py-2 font-mono">#{p.id}</td>
                        <td className="px-3 py-2">
                          <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_CORES[p.status]}`}>
                            {p.status}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-center text-gray-500">{p.itens.length}</td>
                        <td className="px-3 py-2 text-right">R$ {p.total}</td>
                        <td className="px-3 py-2 text-right">
                          {p.status === "rascunho" && (
                            <button
                              type="button"
                              onClick={() => acao(() => api.aprovarCompra(p.id))}
                              className="text-sm font-medium text-blue-600 hover:underline"
                            >
                              Aprovar
                            </button>
                          )}
                          {p.status === "aprovado" && (
                            <button
                              type="button"
                              onClick={() => acao(() => api.receberCompra(p.id))}
                              className="text-sm font-medium text-green-600 hover:underline"
                            >
                              Receber
                            </button>
                          )}
                          {p.status === "recebido" && <span className="text-gray-400">—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
