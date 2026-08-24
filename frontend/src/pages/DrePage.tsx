import { useCallback, useEffect, useMemo, useState } from "react";
import { api, baixarArquivo } from "../api/client";
import type { Dre, Marketplace } from "../types/dre";

const MESES = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

const GRUPO_DEDUCOES = "deducoes";
const GRUPO_OP_ML = "operacional_ml";
const GRUPO_OP_SHOPEE = "operacional_shopee";
const GRUPO_GERAL = "geral";

function brl(v: string): string {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
    : `R$ ${v}`;
}

function pct(v: string): string {
  const n = Number(v);
  return Number.isFinite(n) ? `${n.toLocaleString("pt-BR")}%` : `${v}%`;
}

const hoje = new Date();

export function DrePage() {
  const [ano, setAno] = useState(hoje.getFullYear());
  const [mes, setMes] = useState(hoje.getMonth() + 1);
  const [marketplace, setMarketplace] = useState<Marketplace>("todos");
  const [dre, setDre] = useState<Dre | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro(null);
    try {
      setDre(await api.getDre(ano, mes, marketplace));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao carregar DRE");
    } finally {
      setCarregando(false);
    }
  }, [ano, mes, marketplace]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  // Ao abrir, aponta para a competência mais recente com vendas.
  useEffect(() => {
    api
      .getCompetencias()
      .then((cs) => {
        if (cs.length > 0) {
          setAno(cs[0].ano);
          setMes(cs[0].mes);
        }
      })
      .catch(() => undefined);
  }, []);

  const anos = useMemo(() => {
    const atual = hoje.getFullYear();
    return [atual + 1, atual, atual - 1, atual - 2];
  }, []);

  /** Baixa um arquivo protegido, mostrando o erro na tela se falhar. */
  async function baixar(url: string, nome: string) {
    try {
      await baixarArquivo(url, nome);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao baixar o arquivo");
    }
  }

  async function salvarDespesa(grupo: string, categoria: string, valor: string) {
    await api.salvarDespesaDre({ ano, mes, grupo, categoria, valor: valor || "0" });
    await carregar();
  }

  return (
    <div className="mx-auto max-w-4xl p-6">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">DRE</h1>
          <p className="text-sm text-gray-500">
            Demonstração do resultado por competência.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {(["excel", "pdf"] as const).map((formato) => (
            <button
              key={formato}
              type="button"
              onClick={() =>
                void baixar(
                  api.urlExportDre(ano, mes, marketplace, formato),
                  `dre-${ano}-${String(mes).padStart(2, "0")}.${formato === "excel" ? "xlsx" : "pdf"}`,
                )
              }
              className="rounded-md border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              {formato === "excel" ? "Excel" : "PDF"}
            </button>
          ))}
        </div>
      </header>

      {/* Filtros */}
      <div className="mb-6 flex flex-wrap gap-3">
        <Select label="Ano" value={ano} onChange={(v) => setAno(Number(v))}>
          {anos.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </Select>
        <Select label="Mês" value={mes} onChange={(v) => setMes(Number(v))}>
          {MESES.map((m, i) => (
            <option key={m} value={i + 1}>{m}</option>
          ))}
        </Select>
        <Select
          label="Marketplace"
          value={marketplace}
          onChange={(v) => setMarketplace(v as Marketplace)}
        >
          <option value="todos">Todos</option>
          <option value="Mercado Livre">Mercado Livre</option>
          <option value="Shopee">Shopee</option>
        </Select>
      </div>

      {erro && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {erro}
        </div>
      )}

      {dre && (
        <>
          <Cards dre={dre} />
          <Tabela dre={dre} onSalvar={salvarDespesa} carregando={carregando} />
        </>
      )}
    </div>
  );
}

function Cards({ dre }: { dre: Dre }) {
  const cards = [
    { rotulo: "Receita Líquida", valor: brl(dre.receitas.receita_liquida) },
    { rotulo: "CMV", valor: brl(dre.cmv) },
    { rotulo: "Lucro Líquido", valor: brl(dre.lucro_liquido), destaque: true },
    { rotulo: "Margem Líquida", valor: pct(dre.margens.liquida) },
  ];
  return (
    <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
      {cards.map((c) => (
        <div
          key={c.rotulo}
          className="rounded-lg border border-gray-200 bg-white p-4"
        >
          <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
            {c.rotulo}
          </p>
          <p
            className={`mt-1 text-lg font-semibold ${
              c.destaque
                ? Number(dre.lucro_liquido) >= 0
                  ? "text-emerald-600"
                  : "text-red-600"
                : "text-gray-900"
            }`}
          >
            {c.valor}
          </p>
        </div>
      ))}
    </div>
  );
}

function Tabela({
  dre,
  onSalvar,
  carregando,
}: {
  dre: Dre;
  onSalvar: (grupo: string, categoria: string, valor: string) => Promise<void>;
  carregando: boolean;
}) {
  return (
    <div
      className={`overflow-hidden rounded-lg border border-gray-200 bg-white transition-opacity ${
        carregando ? "opacity-60" : ""
      }`}
    >
      <table className="w-full text-sm">
        <tbody className="divide-y divide-gray-100">
          <SecaoTitulo texto="Receitas" />
          <LinhaValor rotulo="Receita Mercado Livre" valor={dre.receitas.mercado_livre} />
          <LinhaValor rotulo="Receita Shopee" valor={dre.receitas.shopee} />
          <LinhaValor rotulo="Receita Total (Bruta)" valor={dre.receitas.receita_bruta} negrito />
          {Object.entries(dre.receitas.deducoes.itens).map(([cat, val]) => (
            <LinhaEditavel
              key={cat}
              rotulo={`(-) ${cat}`}
              valor={val}
              onSalvar={(v) => onSalvar(GRUPO_DEDUCOES, cat, v)}
            />
          ))}
          <LinhaValor rotulo="Receita Líquida" valor={dre.receitas.receita_liquida} negrito destaque />

          <SecaoTitulo texto="Custo das Mercadorias Vendidas" />
          <LinhaValor rotulo="(-) CMV (automático)" valor={dre.cmv} />
          <LinhaValor rotulo="Lucro Bruto" valor={dre.lucro_bruto} negrito destaque />

          <SecaoTitulo texto="Despesas Operacionais — Mercado Livre" />
          {Object.entries(dre.despesas_operacionais.mercado_livre.itens).map(([cat, val]) => (
            <LinhaEditavel
              key={cat}
              rotulo={cat}
              valor={val}
              onSalvar={(v) => onSalvar(GRUPO_OP_ML, cat, v)}
            />
          ))}

          <SecaoTitulo texto="Despesas Operacionais — Shopee" />
          {Object.entries(dre.despesas_operacionais.shopee.itens).map(([cat, val]) => (
            <LinhaEditavel
              key={cat}
              rotulo={cat}
              valor={val}
              onSalvar={(v) => onSalvar(GRUPO_OP_SHOPEE, cat, v)}
            />
          ))}
          <LinhaValor
            rotulo="Total Despesas Operacionais"
            valor={dre.despesas_operacionais.total}
            negrito
          />
          <LinhaValor rotulo="Lucro Operacional" valor={dre.lucro_operacional} negrito destaque />

          <SecaoTitulo texto="Despesas Gerais" />
          {Object.entries(dre.despesas_gerais.itens).map(([cat, val]) => (
            <LinhaEditavel
              key={cat}
              rotulo={cat}
              valor={val}
              onSalvar={(v) => onSalvar(GRUPO_GERAL, cat, v)}
            />
          ))}
          <LinhaValor rotulo="Total Despesas Gerais" valor={dre.despesas_gerais.total} negrito />

          <SecaoTitulo texto="Resultado" />
          <LinhaValor rotulo="Lucro Líquido" valor={dre.lucro_liquido} negrito destaque />
          <LinhaValor rotulo="EBITDA" valor={dre.ebitda} />
          <LinhaMargem rotulo="Margem Bruta" valor={dre.margens.bruta} />
          <LinhaMargem rotulo="Margem Operacional" valor={dre.margens.operacional} />
          <LinhaMargem rotulo="Margem Líquida" valor={dre.margens.liquida} />
        </tbody>
      </table>
    </div>
  );
}

function SecaoTitulo({ texto }: { texto: string }) {
  return (
    <tr className="bg-gray-50">
      <td colSpan={2} className="px-4 py-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
        {texto}
      </td>
    </tr>
  );
}

function LinhaValor({
  rotulo,
  valor,
  negrito = false,
  destaque = false,
}: {
  rotulo: string;
  valor: string;
  negrito?: boolean;
  destaque?: boolean;
}) {
  const n = Number(valor);
  const cor = destaque ? (n >= 0 ? "text-emerald-600" : "text-red-600") : "text-gray-900";
  return (
    <tr>
      <td className={`px-4 py-2 ${negrito ? "font-semibold text-gray-900" : "text-gray-600"}`}>
        {rotulo}
      </td>
      <td className={`px-4 py-2 text-right tabular-nums ${negrito ? "font-semibold" : ""} ${cor}`}>
        {brl(valor)}
      </td>
    </tr>
  );
}

function LinhaMargem({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <tr>
      <td className="px-4 py-2 text-gray-600">{rotulo}</td>
      <td className="px-4 py-2 text-right font-medium tabular-nums text-gray-900">
        {pct(valor)}
      </td>
    </tr>
  );
}

function LinhaEditavel({
  rotulo,
  valor,
  onSalvar,
}: {
  rotulo: string;
  valor: string;
  onSalvar: (valor: string) => Promise<void>;
}) {
  const [rascunho, setRascunho] = useState(valor);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => setRascunho(valor), [valor]);

  async function commit() {
    if (rascunho === valor) return;
    setSalvando(true);
    try {
      await onSalvar(rascunho);
    } finally {
      setSalvando(false);
    }
  }

  return (
    <tr>
      <td className="px-4 py-1.5 text-gray-600">{rotulo}</td>
      <td className="px-4 py-1.5 text-right">
        <div className="flex items-center justify-end gap-1">
          <span className="text-gray-400">R$</span>
          <input
            type="number"
            step="0.01"
            value={rascunho}
            disabled={salvando}
            onChange={(e) => setRascunho(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
            className="w-28 rounded border border-gray-200 px-2 py-1 text-right tabular-nums text-gray-900 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-200"
          />
        </div>
      </td>
    </tr>
  );
}

function Select({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string | number;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs font-medium text-gray-500">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm font-normal text-gray-900 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-200"
      >
        {children}
      </select>
    </label>
  );
}
