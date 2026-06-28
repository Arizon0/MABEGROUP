import { useState } from "react";
import { api } from "../api/client";
import type { FiltroRelatorio } from "../api/client";
import type { TipoRelatorio } from "../types/dashboard";

const TIPOS: { valor: TipoRelatorio; rotulo: string }[] = [
  { valor: "dre", rotulo: "DRE Simplificado" },
  { valor: "ranking", rotulo: "Ranking por Receita Líquida" },
  { valor: "giro", rotulo: "Giro de Estoque" },
  { valor: "fluxo-caixa", rotulo: "Fluxo de Caixa" },
];

type Linha = Record<string, unknown>;

export function RelatoriosPage() {
  const [tipo, setTipo] = useState<TipoRelatorio>("dre");
  const [filtro, setFiltro] = useState<FiltroRelatorio>({});
  const [linhas, setLinhas] = useState<Linha[]>([]);
  const [colunas, setColunas] = useState<string[]>([]);
  const [erro, setErro] = useState<string | null>(null);

  async function gerar() {
    setErro(null);
    try {
      const payload = await api.getRelatorio<unknown>(tipo, filtro);
      const rows: Linha[] = Array.isArray(payload)
        ? (payload as Linha[])
        : Object.entries(payload as Record<string, unknown>).map(([conta, valor]) => ({
            conta,
            valor,
          }));
      setLinhas(rows);
      setColunas(rows.length ? Object.keys(rows[0]) : []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao gerar relatório");
      setLinhas([]);
      setColunas([]);
    }
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Relatórios</h1>
        <p className="text-sm text-gray-500">
          DRE, ranking, giro e fluxo de caixa — com filtro de período e canal.
        </p>
      </header>

      <div className="mb-4 flex flex-wrap items-end gap-3 rounded border border-gray-200 bg-white p-4">
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          Relatório
          <select
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoRelatorio)}
            className="input"
          >
            {TIPOS.map((t) => (
              <option key={t.valor} value={t.valor}>
                {t.rotulo}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          Início
          <input
            type="date"
            onChange={(e) => setFiltro({ ...filtro, data_inicio: e.target.value || undefined })}
            className="input"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          Fim
          <input
            type="date"
            onChange={(e) => setFiltro({ ...filtro, data_fim: e.target.value || undefined })}
            className="input"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          Canal
          <select
            onChange={(e) => setFiltro({ ...filtro, canal: e.target.value || undefined })}
            className="input"
          >
            <option value="">Todos</option>
            <option value="Mercado Livre">Mercado Livre</option>
            <option value="Shopee">Shopee</option>
          </select>
        </label>
        <button
          type="button"
          onClick={gerar}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Gerar
        </button>
        <div className="ml-auto flex gap-2">
          <a
            href={api.urlRelatorio(tipo, "excel", filtro)}
            className="rounded border border-green-600 px-3 py-2 text-sm font-medium text-green-700 hover:bg-green-50"
          >
            Excel
          </a>
          <a
            href={api.urlRelatorio(tipo, "pdf", filtro)}
            className="rounded border border-red-600 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
          >
            PDF
          </a>
        </div>
      </div>

      {erro && (
        <div className="mb-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {erro}
        </div>
      )}

      {linhas.length > 0 && (
        <div className="overflow-hidden rounded border border-gray-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                {colunas.map((c) => (
                  <th key={c} className="px-3 py-2">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {linhas.map((linha, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  {colunas.map((c) => (
                    <td key={c} className="px-3 py-2 text-gray-700">
                      {linha[c] === null || linha[c] === undefined ? "—" : String(linha[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
