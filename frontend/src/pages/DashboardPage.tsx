import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Dashboard, DRE, RankingReceita } from "../types/dashboard";
import type { Dre } from "../types/dre";

const MESES = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

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

function inteiro(v: number | string): string {
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString("pt-BR") : String(v);
}

function rotuloMes(ano: number, mesNum: number): string {
  return `${MESES[mesNum - 1]} ${ano}`;
}

export function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [dre, setDre] = useState<DRE | null>(null);
  const [ranking, setRanking] = useState<RankingReceita[]>([]);
  const [dreMes, setDreMes] = useState<Dre | null>(null);
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

  // DRE da competência mais recente — busca independente para nunca bloquear
  // o restante do dashboard caso o módulo DRE ainda não tenha dados.
  useEffect(() => {
    (async () => {
      try {
        const comps = await api.getCompetencias();
        if (comps.length === 0) return;
        const { ano, mes } = comps[0];
        setDreMes(await api.getDre(ano, mes, "todos"));
      } catch {
        // silencioso — o dashboard principal segue funcionando
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
          <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-4">
            <Kpi titulo="Faturamento bruto" valor={brl(data.faturamento_bruto)} />
            <Kpi titulo="Líquido recebido" valor={brl(data.liquido_total)} />
            <Kpi
              titulo="Lucro estimado"
              valor={brl(data.lucro_estimado)}
              cor={Number(data.lucro_estimado) >= 0 ? "text-green-600" : "text-red-600"}
            />
            <Kpi titulo="CMV total" valor={brl(data.custo_produtos_vendidos)} />
          </div>

          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Kpi
              titulo="Qtd. de vendas"
              valor={inteiro(data.qtd_pedidos)}
              legenda="pedidos únicos"
            />
            <Kpi
              titulo="Unidades vendidas"
              valor={inteiro(data.unidades_vendidas)}
              legenda="itens"
            />
            <Kpi
              titulo="Produtos distintos"
              valor={inteiro(data.produtos_distintos)}
              legenda="SKUs vendidos"
            />
            <Kpi
              titulo="CMV do mês vigente"
              valor={data.mes_vigente ? brl(data.mes_vigente.cmv) : "—"}
              legenda={
                data.mes_vigente
                  ? rotuloMes(data.mes_vigente.ano, data.mes_vigente.mes_num)
                  : undefined
              }
            />
          </div>

          <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
            <Painel titulo="Entradas">
              <ul className="space-y-1.5 text-sm">
                <MovLinha rotulo="Receita bruta" valor={data.entradas.receita_bruta} entrada />
                <MovLinha rotulo="Descontos e bônus" valor={data.entradas.descontos_bonus} entrada />
                <li className="mt-1 flex justify-between border-t border-gray-100 pt-1.5">
                  <span className="font-semibold text-gray-700">Total de entradas</span>
                  <span className="font-bold text-green-700">
                    {brl(
                      String(
                        Number(data.entradas.receita_bruta) +
                          Number(data.entradas.descontos_bonus),
                      ),
                    )}
                  </span>
                </li>
              </ul>
            </Painel>

            <Painel titulo="Saídas">
              <ul className="space-y-1.5 text-sm">
                <MovLinha rotulo="Tarifas de plataforma" valor={data.saidas.tarifas_plataforma} />
                <MovLinha rotulo="Frete líquido" valor={data.saidas.frete_liquido} />
                <MovLinha rotulo="Cancelamentos" valor={data.saidas.cancelamentos} />
                <MovLinha rotulo="CMV (custo dos produtos)" valor={`-${data.saidas.custo_produtos_vendidos}`} />
                {Number(data.saidas.custos_operacionais) !== 0 && (
                  <MovLinha rotulo="Custos operacionais" valor={`-${data.saidas.custos_operacionais}`} />
                )}
              </ul>
            </Painel>
          </div>

          {dreMes && (
            <div className="mb-6">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase text-gray-500">
                  DRE ·{" "}
                  {MESES[dreMes.competencia.mes - 1]} {dreMes.competencia.ano}
                </h2>
                <Link to="/dre" className="text-sm font-medium text-blue-600 hover:underline">
                  Abrir DRE →
                </Link>
              </div>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Kpi titulo="Receita líquida" valor={brl(dreMes.receitas.receita_liquida)} />
                <Kpi titulo="CMV" valor={brl(dreMes.cmv)} />
                <Kpi
                  titulo="Lucro líquido"
                  valor={brl(dreMes.lucro_liquido)}
                  cor={Number(dreMes.lucro_liquido) >= 0 ? "text-green-600" : "text-red-600"}
                />
                <Kpi titulo="Margem líquida" valor={pct(dreMes.margens.liquida)} />
              </div>
            </div>
          )}

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

          {data.resumo_mensal.length > 0 && (
            <div className="mt-6">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase text-gray-500">
                  Resumo detalhado por mês
                </h2>
                <span className="text-xs text-gray-400">
                  Conferência: líquido importado vs. soma dos componentes
                </span>
              </div>
              <div className="overflow-x-auto rounded border border-gray-200 bg-white">
                <table className="w-full whitespace-nowrap text-sm">
                  <thead className="border-b border-gray-200 bg-gray-50 text-left text-xs uppercase text-gray-500">
                    <tr>
                      <th className="px-3 py-2">Mês</th>
                      <th className="px-3 py-2 text-right">Vendas</th>
                      <th className="px-3 py-2 text-right">Unid.</th>
                      <th className="px-3 py-2 text-right">SKUs</th>
                      <th className="px-3 py-2 text-right">Receita bruta</th>
                      <th className="px-3 py-2 text-right">Tarifas</th>
                      <th className="px-3 py-2 text-right">Frete líq.</th>
                      <th className="px-3 py-2 text-right">Descontos</th>
                      <th className="px-3 py-2 text-right">Cancel.</th>
                      <th className="px-3 py-2 text-right">Líquido</th>
                      <th className="px-3 py-2 text-right">CMV</th>
                      <th className="px-3 py-2 text-right">Lucro bruto</th>
                      <th className="px-3 py-2 text-right">Margem</th>
                      <th className="px-3 py-2 text-center">Confere?</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.resumo_mensal.map((m) => (
                      <tr key={m.mes} className="hover:bg-gray-50">
                        <td className="px-3 py-2 font-medium text-gray-900">
                          {rotuloMes(m.ano, m.mes_num)}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-700">{inteiro(m.pedidos)}</td>
                        <td className="px-3 py-2 text-right text-gray-700">{inteiro(m.unidades)}</td>
                        <td className="px-3 py-2 text-right text-gray-700">{inteiro(m.produtos_distintos)}</td>
                        <td className="px-3 py-2 text-right text-gray-900">{brl(m.receita_bruta)}</td>
                        <td className="px-3 py-2 text-right text-red-600">{brl(m.tarifas_plataforma)}</td>
                        <td className="px-3 py-2 text-right text-red-600">{brl(m.frete_liquido)}</td>
                        <td className="px-3 py-2 text-right text-green-700">{brl(m.descontos)}</td>
                        <td className="px-3 py-2 text-right text-red-600">{brl(m.cancelamentos)}</td>
                        <td className="px-3 py-2 text-right font-semibold text-gray-900">{brl(m.liquido_recebido)}</td>
                        <td className="px-3 py-2 text-right text-red-600">{brl(m.cmv)}</td>
                        <td
                          className={`px-3 py-2 text-right font-semibold ${
                            Number(m.lucro_bruto) >= 0 ? "text-green-700" : "text-red-600"
                          }`}
                        >
                          {brl(m.lucro_bruto)}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-700">{pct(m.margem_liquida)}</td>
                        <td className="px-3 py-2 text-center">
                          {m.conferencia.confere ? (
                            <span
                              className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700"
                              title={`Soma dos componentes ${brl(
                                m.conferencia.soma_componentes,
                              )} = líquido importado ${brl(m.conferencia.liquido_importado)}`}
                            >
                              ✓ OK
                            </span>
                          ) : (
                            <span
                              className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700"
                              title={`Diferença de ${brl(m.conferencia.diferenca)} entre a soma dos componentes e o líquido importado`}
                            >
                              Δ {brl(m.conferencia.diferenca)}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-xs text-gray-400">
                A coluna <span className="font-medium">Confere?</span> valida que{" "}
                <span className="font-medium">
                  Receita bruta + Tarifas + Frete + Descontos + Cancelamentos = Líquido recebido
                </span>{" "}
                (valor importado direto do canal). Lucro bruto = Líquido − CMV.
              </p>
            </div>
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

function Kpi({
  titulo,
  valor,
  cor = "text-gray-900",
  legenda,
}: {
  titulo: string;
  valor: string;
  cor?: string;
  legenda?: string;
}) {
  return (
    <div className="rounded border border-gray-200 bg-white p-4">
      <div className="mb-1 text-xs font-medium uppercase text-gray-500">{titulo}</div>
      <div className={`text-xl font-bold ${cor}`}>{valor}</div>
      {legenda && <div className="mt-0.5 text-xs text-gray-400">{legenda}</div>}
    </div>
  );
}

function MovLinha({ rotulo, valor, entrada = false }: { rotulo: string; valor: string; entrada?: boolean }) {
  return (
    <li className="flex justify-between">
      <span className="text-gray-600">{rotulo}</span>
      <span className={entrada ? "text-green-700" : "text-red-600"}>{brl(valor)}</span>
    </li>
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
