import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Dashboard, DRE, RankingReceita } from "../types/dashboard";

function brl(v: string): string {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
    : `R$ ${v}`;
}

export function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [dre, setDre] = useState<DRE | null>(null);
  const [ranking, setRanking] = useState<RankingReceita[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [d, dreRes, rank] = await Promise.all([
          api.getDashboard(),
          api.getRelatorio<DRE>("dre"),
          api.getRelatorio<RankingReceita[]>("ranking"),
        ]);
        setData(d);
        setDre(dreRes);
        setRanking(rank.slice(0, 10));
      } catch (e) {
        setErro(e instanceof Error ? e.message : "Erro ao carregar dashboard");
      } finally {
        setCarregando(false);
      }
    })();
  }, []);

  const semDados =
    data && Number(data.faturamento_bruto) === 0 && Number(data.unidades_vendidas) === 0;

  return (
    <div className="mx-auto max-w-6xl p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500">Visão geral do desempenho multicanal.</p>
      </header>

      {erro && (
        <div className="mb-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {erro}
        </div>
      )}

      {carregando ? (
        <p className="text-gray-500">Carregando...</p>
      ) : semDados ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-white p-10 text-center">
          <p className="text-lg font-semibold text-gray-700">Nenhuma venda importada ainda</p>
          <p className="mt-1 text-sm text-gray-500">
            Vá em <span className="font-semibold text-blue-600">Importar</span> e suba as
            planilhas do Mercado Livre e da Shopee para ver os números aqui.
          </p>
          <a
            href="/importar"
            className="mt-4 inline-block rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Importar planilhas
          </a>
        </div>
      ) : data ? (
        <>
          <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-4">
            <Kpi titulo="Faturamento bruto" valor={brl(data.faturamento_bruto)} />
            <Kpi titulo="Líquido recebido" valor={brl(data.liquido_total)} />
            <Kpi
              titulo="Lucro estimado"
              valor={brl(data.lucro_estimado)}
              cor={Number(data.lucro_estimado) >= 0 ? "text-green-600" : "text-red-600"}
            />
            <Kpi titulo="Unidades vendidas" valor={data.unidades_vendidas} />
          </div>

          <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Painel titulo="Líquido por canal">
              <ul className="space-y-2">
                {Object.entries(data.liquido_por_canal).map(([canal, valor]) => (
                  <li key={canal} className="flex justify-between text-sm">
                    <span className="text-gray-700">{canal}</span>
                    <span className="font-semibold text-gray-900">{brl(valor)}</span>
                  </li>
                ))}
              </ul>
            </Painel>

            <Painel titulo="Projeção de líquido">
              <ul className="space-y-2">
                {Object.entries(data.projecoes).map(([dias, valor]) => (
                  <li key={dias} className="flex justify-between text-sm">
                    <span className="text-gray-700">{dias} dias</span>
                    <span className="font-semibold text-gray-900">{brl(valor)}</span>
                  </li>
                ))}
              </ul>
            </Painel>

            {dre && (
              <Painel titulo="DRE — resultado">
                <ul className="space-y-1.5 text-sm">
                  <DreLinha rotulo="Receita bruta" valor={dre.receita_bruta} />
                  <DreLinha rotulo="Tarifas" valor={dre.tarifas_plataforma} negativo />
                  <DreLinha rotulo="Frete líquido" valor={dre.frete_liquido} negativo />
                  <DreLinha rotulo="Custo produtos" valor={dre.custo_produtos_vendidos} negativo />
                  <li className="mt-1 flex justify-between border-t border-gray-100 pt-1.5">
                    <span className="font-semibold text-gray-700">Margem bruta</span>
                    <span
                      className={`font-bold ${
                        Number(dre.margem_bruta) >= 0 ? "text-green-700" : "text-red-600"
                      }`}
                    >
                      {brl(dre.margem_bruta)}
                    </span>
                  </li>
                </ul>
              </Painel>
            )}
          </div>

          {ranking.length > 0 && (
            <Painel titulo="Top 10 produtos por líquido recebido">
              <div className="overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="text-left text-xs uppercase text-gray-400">
                    <tr>
                      <th className="pb-2">#</th>
                      <th className="pb-2">SKU</th>
                      <th className="pb-2 text-right">Unidades</th>
                      <th className="pb-2 text-right">Líquido</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {ranking.map((r, i) => (
                      <tr key={r.sku_base}>
                        <td className="py-1.5 text-gray-400">{i + 1}</td>
                        <td className="py-1.5 font-medium text-gray-900">{r.sku_base}</td>
                        <td className="py-1.5 text-right text-gray-700">
                          {Number(r.unidades).toLocaleString("pt-BR")}
                        </td>
                        <td className="py-1.5 text-right font-semibold text-gray-900">
                          {brl(r.liquido)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Painel>
          )}

          <div className="mt-6 rounded border border-gray-200 bg-white p-4 text-sm text-gray-600">
            <span className="font-medium">Custo dos produtos vendidos:</span>{" "}
            {brl(data.custo_produtos_vendidos)} ·{" "}
            <span className="font-medium">Custos operacionais:</span>{" "}
            {brl(data.custos_operacionais)}
          </div>
        </>
      ) : null}
    </div>
  );
}

function Kpi({ titulo, valor, cor = "text-gray-900" }: { titulo: string; valor: string; cor?: string }) {
  return (
    <div className="rounded border border-gray-200 bg-white p-4">
      <div className="mb-1 text-xs font-medium uppercase text-gray-500">{titulo}</div>
      <div className={`text-xl font-bold ${cor}`}>{valor}</div>
    </div>
  );
}

function Painel({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="rounded border border-gray-200 bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase text-gray-500">{titulo}</h2>
      {children}
    </div>
  );
}

function DreLinha({ rotulo, valor, negativo = false }: { rotulo: string; valor: string; negativo?: boolean }) {
  return (
    <li className="flex justify-between">
      <span className="text-gray-600">{rotulo}</span>
      <span className={negativo ? "text-red-600" : "text-gray-900"}>{brl(valor)}</span>
    </li>
  );
}
