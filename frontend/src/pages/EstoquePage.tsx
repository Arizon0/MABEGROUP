import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { RelatorioEstoque, Saldo } from "../types/estoque";

export function EstoquePage() {
  const [saldos, setSaldos] = useState<Saldo[]>([]);
  const [relatorio, setRelatorio] = useState<RelatorioEstoque | null>(null);
  const [busca, setBusca] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  const recarregar = useCallback(async (q?: string) => {
    setCarregando(true);
    setErro(null);
    try {
      const [s, r] = await Promise.all([
        api.listarSaldos(q),
        api.relatorioEstoque(),
      ]);
      setSaldos(s);
      setRelatorio(r);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar estoque");
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void recarregar();
  }, [recarregar]);

  return (
    <div className="mx-auto max-w-5xl p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Estoque</h1>
        <p className="text-sm text-gray-500">Saldo por SKU × local, alertas e valorização.</p>
      </header>

      {erro && (
        <div className="mb-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {erro}
        </div>
      )}

      {relatorio && (
        <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Card titulo="Valor total do estoque">
            <span className="text-2xl font-bold text-gray-900">
              R$ {relatorio.valor_total_estoque}
            </span>
          </Card>
          <Card titulo="Alertas (abaixo do mínimo)">
            <span
              className={`text-2xl font-bold ${
                relatorio.total_alertas > 0 ? "text-red-600" : "text-green-600"
              }`}
            >
              {relatorio.total_alertas}
            </span>
          </Card>
          <Card titulo="Top SKU vendido">
            <span className="text-lg font-semibold text-gray-900">
              {relatorio.ranking_skus[0]?.sku_base ?? "—"}
            </span>
            {relatorio.ranking_skus[0] && (
              <span className="ml-2 text-sm text-gray-500">
                {relatorio.ranking_skus[0].unidades} un
              </span>
            )}
          </Card>
        </div>
      )}

      {relatorio && relatorio.alertas.length > 0 && (
        <div className="mb-6 rounded border border-red-200 bg-red-50 p-3">
          <h2 className="mb-2 text-sm font-semibold text-red-700">
            Produtos abaixo do estoque mínimo
          </h2>
          <ul className="space-y-1 text-sm text-red-700">
            {relatorio.alertas.map((a) => (
              <li key={a.produto_id} className="flex justify-between">
                <span>
                  <span className="font-mono font-semibold">{a.sku_base}</span> — {a.nome}
                </span>
                <span>
                  {a.disponivel_total} / mín {a.estoque_minimo}
                </span>
              </li>
            ))}
          </ul>
        </div>
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
      ) : saldos.length === 0 ? (
        <p className="text-sm text-gray-500">Nenhum saldo de estoque registrado.</p>
      ) : (
        <div className="overflow-hidden rounded border border-gray-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-3 py-2">SKU</th>
                <th className="px-3 py-2">Produto</th>
                <th className="px-3 py-2">Local</th>
                <th className="px-3 py-2 text-right">Disponível</th>
                <th className="px-3 py-2 text-right">Reservado</th>
                <th className="px-3 py-2 text-right">Custo médio</th>
                <th className="px-3 py-2 text-right">Valor total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {saldos.map((s) => {
                const disp = Number(s.qtd_disponivel);
                return (
                  <tr key={`${s.produto_id}-${s.local_id}`} className="hover:bg-gray-50">
                    <td className="px-3 py-2 font-mono font-semibold">{s.sku_base}</td>
                    <td className="px-3 py-2">{s.nome_produto}</td>
                    <td className="px-3 py-2 text-gray-600">{s.local_nome}</td>
                    <td
                      className={`px-3 py-2 text-right font-medium ${
                        disp <= 0 ? "text-red-600" : "text-gray-900"
                      }`}
                    >
                      {s.qtd_disponivel}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-500">{s.qtd_reservada}</td>
                    <td className="px-3 py-2 text-right text-gray-600">R$ {s.custo_medio}</td>
                    <td className="px-3 py-2 text-right">R$ {s.valor_total}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Card({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="rounded border border-gray-200 bg-white p-4">
      <div className="mb-1 text-xs font-medium uppercase text-gray-500">{titulo}</div>
      <div>{children}</div>
    </div>
  );
}
