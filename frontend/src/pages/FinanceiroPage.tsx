import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ResumoConta, ResumoFinanceiro } from "../types/dashboard";

function brl(v: string): string {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
    : `R$ ${v}`;
}

export function FinanceiroPage() {
  const [data, setData] = useState<ResumoFinanceiro | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        setData(await api.getFinanceiro());
      } catch (e) {
        setErro(e instanceof Error ? e.message : "Erro ao carregar financeiro");
      } finally {
        setCarregando(false);
      }
    })();
  }, []);

  return (
    <div className="mx-auto max-w-5xl p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Financeiro</h1>
        <p className="text-sm text-gray-500">Contas a pagar e a receber.</p>
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
          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <ContaCard titulo="A receber" conta={data.a_receber} cor="text-green-600" />
            <ContaCard titulo="A pagar" conta={data.a_pagar} cor="text-red-600" />
          </div>

          <div className="rounded border border-gray-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold uppercase text-gray-500">
                Saldo projetado
              </span>
              <span
                className={`text-xl font-bold ${
                  Number(data.saldo_projetado) >= 0 ? "text-green-600" : "text-red-600"
                }`}
              >
                {brl(data.saldo_projetado)}
              </span>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

function ContaCard({ titulo, conta, cor }: { titulo: string; conta: ResumoConta; cor: string }) {
  return (
    <div className="rounded border border-gray-200 bg-white p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase text-gray-500">{titulo}</h2>
        <span className="text-xs text-gray-400">{conta.quantidade} lançamentos</span>
      </div>
      <div className={`mb-2 text-2xl font-bold ${cor}`}>{brl(conta.total)}</div>
      <div className="flex justify-between text-sm text-gray-600">
        <span>Em aberto: {brl(conta.aberto)}</span>
        <span>Liquidado: {brl(conta.liquidado)}</span>
      </div>
    </div>
  );
}
