import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type {
  Ads,
  Alerta,
  Aliquota,
  AnaliseVendas,
  EscopoAds,
  FiltroAnalise,
  Ordem,
  PedidoAnalisado,
  Recorte,
} from "../types/analiseVendas";

/** Acima disto a margem é considerada saudável (verde); abaixo, apertada. */
const MARGEM_SAUDAVEL = 10;

const RECORTES: { valor: Recorte; rotulo: string; aviso?: boolean }[] = [
  { valor: "todos", rotulo: "Todos" },
  { valor: "negativos", rotulo: "Só negativos" },
  { valor: "sem-custo", rotulo: "Sem custo" },
  { valor: "sem-comissao", rotulo: "Sem comissão" },
  { valor: "sem-frete", rotulo: "Sem frete" },
  { valor: "pacotes", rotulo: "Vários pacotes" },
  { valor: "revisar", rotulo: "A receber não bate", aviso: true },
];

const ORDENACOES: { valor: Ordem; rotulo: string }[] = [
  { valor: "pior-margem-valor", rotulo: "Pior margem R$" },
  { valor: "pior-margem-pct", rotulo: "Pior margem %" },
  { valor: "melhor-margem-valor", rotulo: "Melhor margem R$" },
  { valor: "melhor-margem-pct", rotulo: "Melhor margem %" },
  { valor: "maior-venda", rotulo: "Maior venda" },
  { valor: "maior-frete", rotulo: "Maior frete" },
  { valor: "data", rotulo: "Data" },
];

const EXPLICACAO_ALERTA: Record<Alerta, string> = {
  sem_sku: "Pedido sem SKU mapeado — não dá para calcular o custo.",
  sem_custo: "Produto sem preço de compra cadastrado — a margem está otimista.",
  sem_comissao: "O canal não informou comissão nesta venda.",
  receber_nao_bate:
    "A soma de receita, comissão, frete e descontos não fecha com o líquido informado pelo canal.",
};

const MESES = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

// --------------------------------------------------------------------------- //
// Formatação                                                                    //
// --------------------------------------------------------------------------- //

/** Valores chegam como string decimal; formata sem passar por perda de precisão visível. */
function num(v: string | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function brl(v: string | null | undefined): string {
  const n = num(v);
  return n === null
    ? "—"
    : n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pct(v: string | null | undefined, casas = 2): string {
  const n = num(v);
  return n === null
    ? "—"
    : `${n.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas })}%`;
}

function dataCurta(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

// --------------------------------------------------------------------------- //
// Peças de UI                                                                   //
// --------------------------------------------------------------------------- //

function Chip({
  ativo,
  rotulo,
  contagem,
  aviso,
  onClick,
}: {
  ativo: boolean;
  rotulo: string;
  contagem?: number;
  aviso?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={ativo}
      className={`whitespace-nowrap rounded-full px-3 py-1.5 text-sm font-medium transition ${
        ativo
          ? "bg-slate-900 text-white"
          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
      }`}
    >
      {aviso && <span aria-hidden="true">⚠ </span>}
      {rotulo}
      {contagem !== undefined && contagem > 0 && (
        <span className={ativo ? "ml-1.5 text-slate-300" : "ml-1.5 text-slate-400"}>
          {contagem}
        </span>
      )}
    </button>
  );
}

/** A margem % como pastilha colorida — é a primeira coisa que se lê na linha. */
function PastilhaMargem({ valor }: { valor: string | null }) {
  const n = num(valor);
  if (n === null) {
    return (
      <span
        className="inline-block rounded-full bg-slate-100 px-2 py-0.5 text-sm text-slate-500"
        title="Pedido sem receita — não existe margem percentual."
      >
        —
      </span>
    );
  }
  const estilo =
    n < 0
      ? "bg-red-50 text-red-700"
      : n < MARGEM_SAUDAVEL
        ? "bg-amber-50 text-amber-800"
        : "bg-emerald-50 text-emerald-700";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-sm font-medium tabular-nums ${estilo}`}>
      {pct(valor, 2)} <span aria-hidden="true">{n < 0 ? "↘" : "↗"}</span>
    </span>
  );
}

function BadgeCanal({ canal }: { canal: string }) {
  const ml = canal.toLowerCase().includes("mercado");
  return (
    <span
      title={canal}
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-bold ${
        ml ? "bg-yellow-300 text-yellow-900" : "bg-orange-500 text-white"
      }`}
    >
      {ml ? "ML" : "SHP"}
    </span>
  );
}

function Numero({ children, forte }: { children: React.ReactNode; forte?: boolean }) {
  return (
    <td className={`px-3 py-3 text-right tabular-nums ${forte ? "font-medium text-slate-900" : "text-slate-700"}`}>
      {children}
    </td>
  );
}

// --------------------------------------------------------------------------- //
// Linha da tabela                                                               //
// --------------------------------------------------------------------------- //

function LinhaPedido({
  pedido,
  onSalvarNf,
}: {
  pedido: PedidoAnalisado;
  onSalvarNf: (pedido: PedidoAnalisado, nf: string) => Promise<void>;
}) {
  const [editandoNf, setEditandoNf] = useState(false);
  const [rascunhoNf, setRascunhoNf] = useState(pedido.numero_nf ?? "");

  async function confirmar() {
    setEditandoNf(false);
    if (rascunhoNf.trim() !== (pedido.numero_nf ?? "")) {
      await onSalvarNf(pedido, rascunhoNf.trim());
    }
  }

  return (
    <tr className="border-b border-slate-100 align-top hover:bg-slate-50">
      <th scope="row" className="max-w-xs px-3 py-3 text-left font-normal">
        {editandoNf ? (
          <input
            autoFocus
            className="input w-28 py-0.5 text-sm"
            aria-label="Número da nota fiscal"
            value={rascunhoNf}
            onChange={(e) => setRascunhoNf(e.target.value)}
            onBlur={confirmar}
            onKeyDown={(e) => {
              if (e.key === "Enter") void confirmar();
              if (e.key === "Escape") {
                setRascunhoNf(pedido.numero_nf ?? "");
                setEditandoNf(false);
              }
            }}
          />
        ) : (
          <button
            type="button"
            onClick={() => setEditandoNf(true)}
            className="font-semibold text-slate-900 hover:underline"
            title="Clique para editar o número da nota fiscal"
          >
            {pedido.numero_nf ? `NF ${pedido.numero_nf}` : `Pedido ${pedido.id_pedido_canal}`}
          </button>
        )}
        <p className="mt-0.5 line-clamp-2 text-sm text-slate-600">{pedido.titulo || "—"}</p>
        <p className="mt-0.5 text-xs text-slate-400">
          {pedido.skus.length > 0 ? pedido.skus.join(" · ") : "sem SKU mapeado"}
          {Number(pedido.qtd) > 1 && ` · ${pedido.qtd} un`}
          {pedido.is_pacote_multi && " · pacote"}
        </p>
        {pedido.alertas.length > 0 && (
          <p className="mt-1 flex flex-wrap gap-1">
            {pedido.alertas.map((a) => (
              <span
                key={a}
                title={EXPLICACAO_ALERTA[a]}
                className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900"
              >
                ⚠ {a.replace(/_/g, " ")}
              </span>
            ))}
          </p>
        )}
      </th>
      <td className="whitespace-nowrap px-3 py-3 text-sm text-slate-600 tabular-nums">
        {dataCurta(pedido.data_venda)}
      </td>
      <td className="px-3 py-3">
        <BadgeCanal canal={pedido.canal} />
      </td>
      <td className="whitespace-nowrap px-3 py-3">
        <PastilhaMargem valor={pedido.margem_pct} />
        <span className="mt-0.5 block text-xs text-slate-400 tabular-nums">
          {brl(pedido.margem_valor)}
        </span>
      </td>
      <Numero forte>{brl(pedido.total)}</Numero>
      <Numero>{brl(pedido.custo)}</Numero>
      <Numero>{brl(pedido.frete)}</Numero>
      <Numero>{brl(pedido.comissao)}</Numero>
      <Numero>{brl(pedido.ads)}</Numero>
      <td
        className="px-3 py-3 text-right italic text-slate-500 tabular-nums"
        title={
          pedido.acos_pct === null
            ? "O canal não informou quanto da receita veio de publicidade."
            : "Investimento em Ads sobre a receita atribuída à publicidade."
        }
      >
        {pedido.acos_pct === null ? "—" : pct(pedido.acos_pct)}
      </td>
      <td
        className="px-3 py-3 text-right font-medium text-slate-900 tabular-nums"
        title="Investimento em Ads sobre a receita total do pedido."
      >
        {pedido.tacos_pct === null ? "—" : pct(pedido.tacos_pct)}
      </td>
      <Numero>{brl(pedido.imposto)}</Numero>
    </tr>
  );
}

// --------------------------------------------------------------------------- //
// Painel de parâmetros: alíquota e publicidade                                  //
// --------------------------------------------------------------------------- //

const hoje = new Date();

function PainelParametros({ aoMudar }: { aoMudar: () => void }) {
  const [aberto, setAberto] = useState(false);
  const [aliquotas, setAliquotas] = useState<Aliquota[]>([]);
  const [lancamentos, setLancamentos] = useState<Ads[]>([]);
  const [erro, setErro] = useState<string | null>(null);

  const [aliq, setAliq] = useState({
    ano: hoje.getFullYear(),
    mes: hoje.getMonth() + 1,
    aliquota_pct: "",
  });
  const [ads, setAds] = useState({
    canal: "Mercado Livre",
    ano: hoje.getFullYear(),
    mes: hoje.getMonth() + 1,
    escopo: "canal" as EscopoAds,
    referencia: "",
    valor: "",
    receita_ads: "",
  });

  const carregar = useCallback(async () => {
    try {
      const [as, ls] = await Promise.all([api.listarAliquotas(), api.listarAds()]);
      setAliquotas(as);
      setLancamentos(ls);
      setErro(null);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao carregar parâmetros");
    }
  }, []);

  useEffect(() => {
    if (aberto) void carregar();
  }, [aberto, carregar]);

  async function executar(acao: () => Promise<unknown>) {
    try {
      await acao();
      setErro(null);
      await carregar();
      aoMudar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao salvar");
    }
  }

  return (
    <section className="mb-6 rounded-lg border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setAberto((v) => !v)}
        aria-expanded={aberto}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-sm font-semibold text-slate-900">
          Parâmetros de custo — imposto e publicidade
        </span>
        <span className="text-sm text-slate-500">{aberto ? "Fechar" : "Abrir"}</span>
      </button>

      {aberto && (
        <div className="grid gap-6 border-t border-slate-200 p-4 lg:grid-cols-2">
          {erro && (
            <p role="alert" className="lg:col-span-2 rounded bg-red-50 px-3 py-2 text-sm text-red-700">
              {erro}
            </p>
          )}

          {/* ---- Alíquota ---- */}
          <div>
            <h3 className="mb-1 text-sm font-semibold text-slate-900">Alíquota de imposto</h3>
            <p className="mb-3 text-xs text-slate-500">
              Alíquota efetiva da competência. Vale a partir do mês informado até
              a próxima cadastrada, então mudar de faixa hoje não reescreve o
              imposto que já foi apurado meses atrás.
            </p>
            <form
              className="mb-3 flex flex-wrap items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                void executar(() =>
                  api.salvarAliquota({
                    ano: aliq.ano,
                    mes: aliq.mes,
                    aliquota_pct: aliq.aliquota_pct || "0",
                  }),
                );
              }}
            >
              <label className="text-xs text-slate-600">
                Ano
                <input
                  type="number"
                  className="input mt-0.5 block w-24"
                  value={aliq.ano}
                  onChange={(e) => setAliq({ ...aliq, ano: Number(e.target.value) })}
                />
              </label>
              <label className="text-xs text-slate-600">
                Mês
                <select
                  className="input mt-0.5 block w-32"
                  value={aliq.mes}
                  onChange={(e) => setAliq({ ...aliq, mes: Number(e.target.value) })}
                >
                  {MESES.map((m, i) => (
                    <option key={m} value={i + 1}>{m}</option>
                  ))}
                </select>
              </label>
              <label className="text-xs text-slate-600">
                Alíquota %
                <input
                  className="input mt-0.5 block w-24"
                  inputMode="decimal"
                  placeholder="8,22"
                  value={aliq.aliquota_pct}
                  onChange={(e) =>
                    setAliq({ ...aliq, aliquota_pct: e.target.value.replace(",", ".") })
                  }
                />
              </label>
              <button
                type="submit"
                className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
              >
                Salvar alíquota
              </button>
            </form>

            <ul className="divide-y divide-slate-100 text-sm">
              {aliquotas.length === 0 && (
                <li className="py-2 text-slate-500">
                  Nenhuma alíquota cadastrada — o imposto está saindo zerado.
                </li>
              )}
              {aliquotas.map((a) => (
                <li key={a.id} className="flex items-center justify-between py-2">
                  <span className="text-slate-700">
                    {MESES[a.mes - 1]}/{a.ano} — <strong>{pct(a.aliquota_pct)}</strong>
                  </span>
                  <button
                    type="button"
                    className="text-xs text-red-600 hover:underline"
                    onClick={() => void executar(() => api.excluirAliquota(a.id))}
                  >
                    Excluir
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* ---- Publicidade ---- */}
          <div>
            <h3 className="mb-1 text-sm font-semibold text-slate-900">Investimento em publicidade</h3>
            <p className="mb-3 text-xs text-slate-500">
              O valor é rateado entre os pedidos do mês proporcionalmente à
              receita. Cada pedido é coberto pelo lançamento mais específico:
              anúncio, depois SKU, depois o canal inteiro. A receita atribuída à
              publicidade é opcional — sem ela existe TACOS, mas não ACOS.
            </p>
            <form
              className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-3"
              onSubmit={(e) => {
                e.preventDefault();
                void executar(() =>
                  api.salvarAds({
                    canal: ads.canal,
                    ano: ads.ano,
                    mes: ads.mes,
                    escopo: ads.escopo,
                    referencia: ads.escopo === "canal" ? "" : ads.referencia,
                    valor: ads.valor || "0",
                    receita_ads: ads.receita_ads || null,
                  }),
                );
              }}
            >
              <label className="text-xs text-slate-600">
                Canal
                <select
                  className="input mt-0.5 block w-full"
                  value={ads.canal}
                  onChange={(e) => setAds({ ...ads, canal: e.target.value })}
                >
                  <option>Mercado Livre</option>
                  <option>Shopee</option>
                </select>
              </label>
              <label className="text-xs text-slate-600">
                Ano
                <input
                  type="number"
                  className="input mt-0.5 block w-full"
                  value={ads.ano}
                  onChange={(e) => setAds({ ...ads, ano: Number(e.target.value) })}
                />
              </label>
              <label className="text-xs text-slate-600">
                Mês
                <select
                  className="input mt-0.5 block w-full"
                  value={ads.mes}
                  onChange={(e) => setAds({ ...ads, mes: Number(e.target.value) })}
                >
                  {MESES.map((m, i) => (
                    <option key={m} value={i + 1}>{m}</option>
                  ))}
                </select>
              </label>
              <label className="text-xs text-slate-600">
                Escopo
                <select
                  className="input mt-0.5 block w-full"
                  value={ads.escopo}
                  onChange={(e) => setAds({ ...ads, escopo: e.target.value as EscopoAds })}
                >
                  <option value="canal">Canal inteiro</option>
                  <option value="anuncio">Anúncio</option>
                  <option value="sku">SKU</option>
                </select>
              </label>
              <label className="text-xs text-slate-600">
                Referência
                <input
                  className="input mt-0.5 block w-full disabled:bg-slate-100"
                  placeholder={ads.escopo === "anuncio" ? "MLB123..." : "SKU"}
                  disabled={ads.escopo === "canal"}
                  value={ads.referencia}
                  onChange={(e) => setAds({ ...ads, referencia: e.target.value })}
                />
              </label>
              <label className="text-xs text-slate-600">
                Investido R$
                <input
                  className="input mt-0.5 block w-full"
                  inputMode="decimal"
                  placeholder="0,00"
                  value={ads.valor}
                  onChange={(e) => setAds({ ...ads, valor: e.target.value.replace(",", ".") })}
                />
              </label>
              <label className="col-span-2 text-xs text-slate-600 sm:col-span-2">
                Receita atribuída à publicidade R$ (opcional — habilita o ACOS)
                <input
                  className="input mt-0.5 block w-full"
                  inputMode="decimal"
                  placeholder="0,00"
                  value={ads.receita_ads}
                  onChange={(e) =>
                    setAds({ ...ads, receita_ads: e.target.value.replace(",", ".") })
                  }
                />
              </label>
              <button
                type="submit"
                className="self-end rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
              >
                Salvar investimento
              </button>
            </form>

            <ul className="divide-y divide-slate-100 text-sm">
              {lancamentos.length === 0 && (
                <li className="py-2 text-slate-500">
                  Nenhum investimento lançado — a coluna Ads está zerada.
                </li>
              )}
              {lancamentos.map((l) => (
                <li key={l.id} className="flex items-center justify-between gap-2 py-2">
                  <span className="text-slate-700">
                    {MESES[l.mes - 1]}/{l.ano} · {l.canal} · {l.escopo}
                    {l.referencia && ` ${l.referencia}`} — <strong>R$ {brl(l.valor)}</strong>
                    {l.receita_ads && (
                      <span className="text-slate-500"> (receita ads R$ {brl(l.receita_ads)})</span>
                    )}
                  </span>
                  <button
                    type="button"
                    className="shrink-0 text-xs text-red-600 hover:underline"
                    onClick={() => void executar(() => api.excluirAds(l.id))}
                  >
                    Excluir
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </section>
  );
}

// --------------------------------------------------------------------------- //
// Página                                                                        //
// --------------------------------------------------------------------------- //

const FILTRO_INICIAL: FiltroAnalise = {
  recorte: "todos",
  ordem: "data",
  pagina: 1,
  tamanho: 50,
};

export function AnaliseVendasPage() {
  const [filtro, setFiltro] = useState<FiltroAnalise>(FILTRO_INICIAL);
  const [busca, setBusca] = useState("");
  const [dados, setDados] = useState<AnaliseVendas | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro(null);
    try {
      setDados(await api.getAnaliseVendas(filtro));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao carregar a análise");
    } finally {
      setCarregando(false);
    }
  }, [filtro]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  // A busca só vira requisição depois que o usuário para de digitar — sem isso
  // cada tecla dispararia uma varredura de todos os pedidos do período.
  useEffect(() => {
    const t = setTimeout(() => {
      setFiltro((f) =>
        (f.busca ?? "") === busca.trim() ? f : { ...f, busca: busca.trim() || undefined, pagina: 1 },
      );
    }, 350);
    return () => clearTimeout(t);
  }, [busca]);

  /** Muda um filtro e volta para a primeira página — a antiga não existe mais. */
  function ajustar(mudanca: Partial<FiltroAnalise>) {
    setFiltro((f) => ({ ...f, ...mudanca, pagina: 1 }));
  }

  async function salvarNf(pedido: PedidoAnalisado, nf: string) {
    try {
      await api.salvarNotaFiscal(pedido.canal, pedido.id_pedido_canal, nf || null);
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao gravar a nota fiscal");
    }
  }

  const resumo = dados?.resumo;
  const paginacao = dados?.paginacao;

  const avisos = useMemo(() => {
    const lista: string[] = [];
    if (!resumo) return lista;
    if (Number(resumo.imposto) === 0 && resumo.pedidos > 0) {
      lista.push(
        "Nenhum imposto está sendo aplicado. Cadastre a alíquota da competência em “Parâmetros de custo” — sem ela a margem aparece maior do que é.",
      );
    }
    if (Number(resumo.ads) === 0 && resumo.pedidos > 0) {
      lista.push(
        "Nenhum investimento em publicidade lançado. Enquanto isso, ACOS e TACOS ficam vazios e a margem ignora o custo de Ads.",
      );
    }
    if (Number(resumo.ads_nao_alocado) > 0) {
      lista.push(
        `R$ ${brl(resumo.ads_nao_alocado)} de publicidade não foram rateados: o anúncio ou SKU lançado não teve venda na competência. Esse custo está fora da margem exibida.`,
      );
    }
    return lista;
  }, [resumo]);

  return (
    <div className="mx-auto max-w-[1600px] p-4 sm:p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Análise de Vendas</h1>
        <p className="text-sm text-slate-500">
          Margem real de cada pedido: líquido recebido menos custo do produto,
          publicidade e imposto.
        </p>
      </header>

      <PainelParametros aoMudar={() => void carregar()} />

      {/* ---- Filtros de período, canal e busca ---- */}
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="text-xs font-medium uppercase tracking-wide text-slate-500">
          De
          <input
            type="date"
            className="input mt-1 block"
            value={filtro.data_inicio ?? ""}
            onChange={(e) => ajustar({ data_inicio: e.target.value || undefined })}
          />
        </label>
        <label className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Até
          <input
            type="date"
            className="input mt-1 block"
            value={filtro.data_fim ?? ""}
            onChange={(e) => ajustar({ data_fim: e.target.value || undefined })}
          />
        </label>
        <label className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Canal
          <select
            className="input mt-1 block"
            value={filtro.canal ?? ""}
            onChange={(e) => ajustar({ canal: e.target.value || undefined })}
          >
            <option value="">Todos</option>
            <option value="Mercado Livre">Mercado Livre</option>
            <option value="Shopee">Shopee</option>
          </select>
        </label>
        <label className="min-w-[12rem] flex-1 text-xs font-medium uppercase tracking-wide text-slate-500">
          Buscar
          <input
            className="input mt-1 block w-full"
            placeholder="NF, pedido, SKU, anúncio ou título"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
        </label>
        <div className="flex gap-2">
          <a
            href={api.urlExportAnalise("excel", filtro)}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Excel
          </a>
          <a
            href={api.urlExportAnalise("pdf", filtro)}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            PDF
          </a>
        </div>
      </div>

      {/* ---- Recorte e ordenação ---- */}
      <div className="mb-4 rounded-lg border border-slate-200 bg-white p-3">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Recorte</p>
        <div className="mb-3 flex flex-wrap gap-1">
          {RECORTES.map((r) => (
            <Chip
              key={r.valor}
              rotulo={r.rotulo}
              aviso={r.aviso}
              ativo={filtro.recorte === r.valor}
              contagem={dados?.contagem_por_recorte?.[r.valor]}
              onClick={() => ajustar({ recorte: r.valor })}
            />
          ))}
        </div>

        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Ordenar por
        </p>
        <div className="flex flex-wrap gap-1">
          {ORDENACOES.map((o) => (
            <Chip
              key={o.valor}
              rotulo={o.rotulo}
              ativo={filtro.ordem === o.valor}
              onClick={() => ajustar({ ordem: o.valor })}
            />
          ))}
        </div>
      </div>

      {avisos.map((aviso) => (
        <p key={aviso} className="mb-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">
          ⚠ {aviso}
        </p>
      ))}

      {erro && (
        <p role="alert" className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {erro}
        </p>
      )}

      {/* ---- Linha-resumo ---- */}
      {resumo && paginacao && (
        <p role="status" className="mb-2 text-sm text-slate-600">
          <strong className="text-slate-900">{resumo.pedidos}</strong> pedidos
          {" · "}
          <span className={resumo.negativos > 0 ? "text-red-700" : undefined}>
            {resumo.negativos} negativos ({pct(resumo.pct_negativos, 0)})
          </span>
          {resumo.para_revisar > 0 && (
            <>
              {" · "}
              <span className="text-amber-800">⚠ {resumo.para_revisar} para revisar</span>
            </>
          )}
          {paginacao.total > 0 && (
            <>
              {" · "}mostrando {paginacao.de}–{paginacao.ate}
            </>
          )}
        </p>
      )}

      {/* ---- Tabela ---- */}
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[1100px] border-collapse text-sm">
          <caption className="sr-only">
            Pedidos com margem, custo, frete, comissão, publicidade e imposto
          </caption>
          <thead className="bg-slate-900 text-white">
            <tr>
              <th scope="col" className="px-3 py-2.5 text-left font-semibold">NF / SKU</th>
              <th scope="col" className="px-3 py-2.5 text-left font-semibold">Data</th>
              <th scope="col" className="px-3 py-2.5 text-left font-semibold">Canal</th>
              <th scope="col" className="px-3 py-2.5 text-left font-semibold">Margem %</th>
              <th scope="col" className="px-3 py-2.5 text-right font-semibold">Total</th>
              <th scope="col" className="px-3 py-2.5 text-right font-semibold">Custo</th>
              <th scope="col" className="px-3 py-2.5 text-right font-semibold">Frete</th>
              <th scope="col" className="px-3 py-2.5 text-right font-semibold">Comissão</th>
              <th scope="col" className="px-3 py-2.5 text-right font-semibold">Ads</th>
              <th scope="col" className="px-3 py-2.5 text-right font-semibold">ACOS</th>
              <th scope="col" className="px-3 py-2.5 text-right font-semibold">TACOS</th>
              <th scope="col" className="px-3 py-2.5 text-right font-semibold">Imposto</th>
            </tr>
          </thead>
          <tbody>
            {dados?.pedidos.map((p) => (
              <LinhaPedido key={`${p.canal}-${p.id_pedido_canal}`} pedido={p} onSalvarNf={salvarNf} />
            ))}
            {!carregando && dados?.pedidos.length === 0 && (
              <tr>
                <td colSpan={12} className="px-3 py-10 text-center text-slate-500">
                  Nenhum pedido neste recorte.
                </td>
              </tr>
            )}
            {carregando && !dados && (
              <tr>
                <td colSpan={12} className="px-3 py-10 text-center text-slate-500">
                  Carregando…
                </td>
              </tr>
            )}
          </tbody>
          {resumo && resumo.pedidos > 0 && (
            <tfoot className="border-t-2 border-slate-300 bg-slate-50 font-medium text-slate-900">
              <tr>
                <th scope="row" colSpan={4} className="px-3 py-3 text-left">
                  Total do recorte
                  <span className="ml-2 font-normal text-slate-500">
                    margem {brl(resumo.margem_valor)} ({pct(resumo.margem_pct)})
                  </span>
                </th>
                <Numero forte>{brl(resumo.total)}</Numero>
                <Numero forte>{brl(resumo.custo)}</Numero>
                <Numero forte>{brl(resumo.frete)}</Numero>
                <Numero forte>{brl(resumo.comissao)}</Numero>
                <Numero forte>{brl(resumo.ads)}</Numero>
                <td />
                <td />
                <Numero forte>{brl(resumo.imposto)}</Numero>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {/* ---- Paginação ---- */}
      {paginacao && paginacao.paginas > 1 && (
        <nav className="mt-4 flex items-center justify-center gap-3" aria-label="Paginação">
          <button
            type="button"
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm disabled:opacity-40"
            disabled={paginacao.pagina <= 1}
            onClick={() => setFiltro((f) => ({ ...f, pagina: (f.pagina ?? 1) - 1 }))}
          >
            Anterior
          </button>
          <span className="text-sm text-slate-600">
            Página {paginacao.pagina} de {paginacao.paginas}
          </span>
          <button
            type="button"
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm disabled:opacity-40"
            disabled={paginacao.pagina >= paginacao.paginas}
            onClick={() => setFiltro((f) => ({ ...f, pagina: (f.pagina ?? 1) + 1 }))}
          >
            Próxima
          </button>
        </nav>
      )}
    </div>
  );
}
