import { useRef, useState } from "react";
import { api } from "../api/client";
import type { ResultadoEstoque, ResultadoImportacao } from "../types/importacao";

function brl(v: string): string {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
    : `R$ ${v}`;
}

type Canal = "ml" | "shopee";

interface CardConfig {
  canal: Canal;
  titulo: string;
  descricao: string;
  arquivoEsperado: string;
  cor: string;
}

const CARDS: CardConfig[] = [
  {
    canal: "ml",
    titulo: "Mercado Livre",
    descricao: "Relatório de vendas exportado do Mercado Livre.",
    arquivoEsperado: "Vendas_BR_MercadoLibre_*.xlsx",
    cor: "border-yellow-300 bg-yellow-50",
  },
  {
    canal: "shopee",
    titulo: "Shopee",
    descricao: "Relatório de pedidos (Order.all) exportado da Shopee.",
    arquivoEsperado: "Order.all_*.xlsx",
    cor: "border-orange-300 bg-orange-50",
  },
];

export function ImportarPage() {
  return (
    <div className="mx-auto max-w-5xl p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Importar planilhas</h1>
        <p className="text-sm text-gray-500">
          Suba os relatórios de vendas de cada canal. O sistema resolve os SKUs,
          lança os recebíveis e atualiza o estoque automaticamente.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {CARDS.map((c) => (
          <ImportCard key={c.canal} config={c} />
        ))}
      </div>

      <SimplesCard />
      <EstoqueCard />
    </div>
  );
}

function EstoqueCard() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<ResultadoEstoque | null>(null);

  async function enviar(arquivo: File) {
    setEnviando(true);
    setErro(null);
    setResultado(null);
    try {
      setResultado(await api.importarEstoque(arquivo));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao importar");
    } finally {
      setEnviando(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  const naoEncontrados = resultado?.nao_encontrados ?? [];

  return (
    <div className="mt-6 rounded-lg border border-emerald-200 bg-emerald-50 p-5">
      <h2 className="text-lg font-bold text-gray-900">Estoque atual</h2>
      <p className="mt-1 text-sm text-gray-600">
        Suba a planilha com o estoque que você tem hoje, por local. Colunas:{" "}
        <span className="font-mono text-xs">SKU</span> (ou{" "}
        <span className="font-mono text-xs">Código</span>/
        <span className="font-mono text-xs">Nome</span>),{" "}
        <span className="font-mono text-xs">Galpão</span> e{" "}
        <span className="font-mono text-xs">ML Full</span> (quantidade em cada local) e{" "}
        <span className="font-mono text-xs">Custo</span> (opcional). Também aceita uma
        coluna <span className="font-mono text-xs">Quantidade</span> única ou uma coluna{" "}
        <span className="font-mono text-xs">Local</span>. Cada saldo é ajustado e valorizado,
        entrando no valor do estoque, no giro e nos alertas.
      </p>

      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,.xls,.csv"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) enviar(f);
        }}
      />
      <button
        type="button"
        disabled={enviando}
        onClick={() => inputRef.current?.click()}
        className="mt-4 rounded bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
      >
        {enviando ? "Importando..." : "Escolher planilha e importar"}
      </button>

      {erro && (
        <div className="mt-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {erro}
        </div>
      )}

      {resultado && (
        <div className="mt-4 rounded border border-green-300 bg-white p-4 text-sm">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
            <Linha rotulo="Saldos atualizados" valor={String(resultado.atualizados)} />
            <Linha rotulo="Novos saldos" valor={String(resultado.saldos_criados)} />
            <Linha rotulo="Unidades em estoque" valor={resultado.unidades_total} />
            <Linha rotulo="Valor do estoque" valor={brl(resultado.valor_total)} destaque />
          </dl>
          {resultado.por_local.length > 0 && (
            <div className="mt-3 border-t border-gray-100 pt-3">
              <p className="mb-1 text-xs font-semibold uppercase text-gray-400">Por local</p>
              <dl className="grid grid-cols-1 gap-y-1">
                {resultado.por_local.map((pl) => (
                  <Linha
                    key={pl.local}
                    rotulo={pl.local}
                    valor={`${pl.unidades} un · ${brl(pl.valor)}`}
                  />
                ))}
              </dl>
            </div>
          )}
          {naoEncontrados.length > 0 && (
            <div className="mt-3 rounded bg-amber-50 px-3 py-2 text-xs text-amber-700">
              <span className="font-semibold">SKU não encontrado no cadastro:</span>{" "}
              {naoEncontrados.join(", ")}. Cadastre esses produtos em{" "}
              <span className="font-semibold">Produtos</span> e importe novamente.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SimplesCard() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<ResultadoImportacao | null>(null);

  async function enviar(arquivo: File) {
    setEnviando(true);
    setErro(null);
    setResultado(null);
    try {
      setResultado(await api.importarVendasSimples(arquivo));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao importar");
    } finally {
      setEnviando(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  const naoCadastrados = resultado?.skus_nao_cadastrados ?? [];

  return (
    <div className="mt-6 rounded-lg border border-blue-200 bg-blue-50 p-5">
      <h2 className="text-lg font-bold text-gray-900">Vendas — planilha simples</h2>
      <p className="mt-1 text-sm text-gray-600">
        Formato genérico para a DRE. Colunas: <span className="font-mono text-xs">SKU</span>,{" "}
        <span className="font-mono text-xs">Preço de Venda</span>,{" "}
        <span className="font-mono text-xs">Quantidade Vendida</span>,{" "}
        <span className="font-mono text-xs">Marketplace</span>,{" "}
        <span className="font-mono text-xs">Data</span>. O CMV é congelado pelo custo do produto.
      </p>

      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,.xls,.csv"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) enviar(f);
        }}
      />
      <button
        type="button"
        disabled={enviando}
        onClick={() => inputRef.current?.click()}
        className="mt-4 rounded bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {enviando ? "Importando..." : "Escolher planilha e importar"}
      </button>

      {erro && (
        <div className="mt-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {erro}
        </div>
      )}

      {resultado && (
        <div className="mt-4 rounded border border-green-300 bg-white p-4 text-sm">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
            <Linha rotulo="Linhas no arquivo" valor={String(resultado.linhas_arquivo)} />
            <Linha rotulo="Vendas inseridas" valor={String(resultado.vendas_inseridas)} />
            <Linha rotulo="Duplicados ignorados" valor={String(resultado.pedidos_duplicados)} />
            {resultado.cmv_total && <Linha rotulo="CMV total" valor={brl(resultado.cmv_total)} />}
          </dl>
          {naoCadastrados.length > 0 && (
            <div className="mt-3 rounded bg-amber-50 px-3 py-2 text-xs text-amber-700">
              <span className="font-semibold">SKU não cadastrado:</span>{" "}
              {naoCadastrados.join(", ")}. Cadastre esses produtos em{" "}
              <span className="font-semibold">Produtos</span> antes de consolidar a DRE.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ImportCard({ config }: { config: CardConfig }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<ResultadoImportacao | null>(null);
  const [nomeArquivo, setNomeArquivo] = useState<string | null>(null);

  async function enviar(arquivo: File) {
    setEnviando(true);
    setErro(null);
    setResultado(null);
    setNomeArquivo(arquivo.name);
    try {
      const res =
        config.canal === "ml"
          ? await api.importarML(arquivo)
          : await api.importarShopee(arquivo);
      setResultado(res);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao importar");
    } finally {
      setEnviando(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className={`rounded-lg border ${config.cor} p-5`}>
      <h2 className="text-lg font-bold text-gray-900">{config.titulo}</h2>
      <p className="mt-1 text-sm text-gray-600">{config.descricao}</p>
      <p className="mt-1 font-mono text-xs text-gray-400">{config.arquivoEsperado}</p>

      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,.xls"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) enviar(f);
        }}
      />

      <button
        type="button"
        disabled={enviando}
        onClick={() => inputRef.current?.click()}
        className="mt-4 w-full rounded bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {enviando ? "Importando..." : "Escolher planilha e importar"}
      </button>

      {nomeArquivo && !enviando && (
        <p className="mt-2 truncate text-xs text-gray-500">Arquivo: {nomeArquivo}</p>
      )}

      {erro && (
        <div className="mt-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {erro}
        </div>
      )}

      {resultado && <Resumo r={resultado} />}
    </div>
  );
}

function Resumo({ r }: { r: ResultadoImportacao }) {
  return (
    <div className="mt-4 rounded border border-green-300 bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-green-600 text-xs font-bold text-white">
          ✓
        </span>
        <span className="text-sm font-semibold text-green-800">
          Importação concluída
        </span>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <Linha rotulo="Linhas no arquivo" valor={String(r.linhas_arquivo)} />
        <Linha rotulo="Vendas inseridas" valor={String(r.vendas_inseridas)} />
        <Linha rotulo="Duplicados ignorados" valor={String(r.pedidos_duplicados)} />
        <Linha rotulo="SKUs resolvidos" valor={String(r.skus_resolvidos)} />
        <Linha
          rotulo="SKUs pendentes"
          valor={String(r.skus_pendentes)}
          alerta={r.skus_pendentes > 0}
        />
        <Linha rotulo="Baixas de estoque" valor={String(r.baixas_estoque)} />
      </dl>

      <div className="mt-3 border-t border-gray-100 pt-3">
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
          <Linha rotulo="Unidades" valor={r.totais.unidades} />
          <Linha rotulo="Receita bruta" valor={brl(r.totais.receita_bruta)} />
          <Linha rotulo="Tarifas plataforma" valor={brl(r.totais.tarifas_plataforma)} />
          <Linha rotulo="Frete líquido" valor={brl(r.totais.frete_liquido)} />
          <Linha
            rotulo="Líquido recebido"
            valor={brl(r.totais.liquido_recebido)}
            destaque
          />
        </div>
      </div>

      {r.skus_pendentes > 0 && (
        <p className="mt-3 rounded bg-amber-50 px-3 py-2 text-xs text-amber-700">
          Há {r.skus_pendentes} SKU(s) sem mapeamento. Vá em{" "}
          <span className="font-semibold">Mapa de SKUs</span> para vinculá-los a um
          produto — as vendas foram importadas mesmo assim.
        </p>
      )}
    </div>
  );
}

function Linha({
  rotulo,
  valor,
  destaque = false,
  alerta = false,
}: {
  rotulo: string;
  valor: string;
  destaque?: boolean;
  alerta?: boolean;
}) {
  return (
    <div className="flex justify-between">
      <dt className="text-gray-500">{rotulo}</dt>
      <dd
        className={`font-semibold ${
          alerta ? "text-amber-600" : destaque ? "text-green-700" : "text-gray-900"
        }`}
      >
        {valor}
      </dd>
    </div>
  );
}
