import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Dashboard } from "../types/dashboard";

function brl(v: string): string {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
    : `R$ ${v}`;
}

export function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        setData(await api.getDashboard());
      } catch (e) {
        setErro(e instanceof Error ? e.message : "Erro ao carregar dashboard");
      } finally {
        setCarregando(false);
      }
    })();
  }, []);

  return (
    <div className="mx-auto max-w-5xl p-6">
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

          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="rounded border border-gray-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-semibold uppercase text-gray-500">
                Líquido por canal
              </h2>
              <ul className="space-y-2">
                {Object.entries(data.liquido_por_canal).map(([canal, valor]) => (
                  <li key={canal} className="flex justify-between text-sm">
                    <span className="text-gray-700">{canal}</span>
                    <span className="font-semibold text-gray-900">{brl(valor)}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded border border-gray-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-semibold uppercase text-gray-500">
                Projeção de líquido
              </h2>
              <ul className="space-y-2">
                {Object.entries(data.projecoes).map(([dias, valor]) => (
                  <li key={dias} className="flex justify-between text-sm">
                    <span className="text-gray-700">{dias} dias</span>
                    <span className="font-semibold text-gray-900">{brl(valor)}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="rounded border border-gray-200 bg-white p-4 text-sm text-gray-600">
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
