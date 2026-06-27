import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { ProdutoBusca } from "../components/ProdutoBusca";
import type { Produto, SkuMap, SkuPendencia } from "../types/skuMap";

function CanalBadge({ canal }: { canal: string }) {
  const cor =
    canal === "Shopee"
      ? "bg-orange-100 text-orange-800"
      : "bg-yellow-100 text-yellow-800";
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${cor}`}>{canal}</span>
  );
}

/**
 * Tela "Mapa de SKUs" (prioridade máxima do frontend):
 *  - Lista de sku_canal sem mapeamento (pendências)
 *  - Busca de sku_base no cadastro de produtos
 *  - Salva o mapeamento e exibe os de-para já configurados
 */
export function SkuMapPage() {
  const [pendencias, setPendencias] = useState<SkuPendencia[]>([]);
  const [mapeamentos, setMapeamentos] = useState<SkuMap[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const recarregar = useCallback(async () => {
    setCarregando(true);
    setErro(null);
    try {
      const [pend, maps] = await Promise.all([
        api.listarPendencias(),
        api.listarSkuMap(),
      ]);
      setPendencias(pend);
      setMapeamentos(maps);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar dados");
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void recarregar();
  }, [recarregar]);

  async function mapear(pendencia: SkuPendencia, produto: Produto) {
    setErro(null);
    try {
      await api.salvarSkuMap({
        sku_canal: pendencia.sku_canal,
        canal: pendencia.canal,
        id_anuncio: pendencia.id_anuncio,
        produto_id: produto.id,
      });
      await recarregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar mapeamento");
    }
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Mapa de SKUs</h1>
        <p className="text-sm text-gray-500">
          Vincule os códigos vindos dos canais (Mercado Livre / Shopee) ao SKU base
          do ERP.
        </p>
      </header>

      {erro && (
        <div className="mb-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {erro}
        </div>
      )}

      {carregando ? (
        <p className="text-gray-500">Carregando...</p>
      ) : (
        <>
          <section className="mb-8">
            <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-gray-800">
              Pendências
              <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700">
                {pendencias.length}
              </span>
            </h2>

            {pendencias.length === 0 ? (
              <p className="rounded border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
                Nenhuma pendência — todos os SKUs estão mapeados. 🎉
              </p>
            ) : (
              <div className="overflow-hidden rounded border border-gray-200">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
                    <tr>
                      <th className="px-3 py-2">SKU do canal</th>
                      <th className="px-3 py-2">Canal</th>
                      <th className="px-3 py-2">Título</th>
                      <th className="px-3 py-2 text-center">Ocorr.</th>
                      <th className="px-3 py-2 w-72">Mapear para</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {pendencias.map((p) => (
                      <tr key={p.id} className="hover:bg-gray-50">
                        <td className="px-3 py-2 font-mono font-semibold">{p.sku_canal}</td>
                        <td className="px-3 py-2">
                          <CanalBadge canal={p.canal} />
                        </td>
                        <td className="px-3 py-2 max-w-xs truncate text-gray-600">
                          {p.titulo ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-center text-gray-500">
                          {p.ocorrencias}
                        </td>
                        <td className="px-3 py-2">
                          <ProdutoBusca onSelecionar={(prod) => mapear(p, prod)} />
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
              De-para configurados ({mapeamentos.length})
            </h2>
            {mapeamentos.length === 0 ? (
              <p className="text-sm text-gray-500">Nenhum mapeamento configurado ainda.</p>
            ) : (
              <div className="overflow-hidden rounded border border-gray-200">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
                    <tr>
                      <th className="px-3 py-2">SKU do canal</th>
                      <th className="px-3 py-2">Canal</th>
                      <th className="px-3 py-2">Anúncio</th>
                      <th className="px-3 py-2">SKU base (ERP)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {mapeamentos.map((m) => (
                      <tr key={m.id} className="hover:bg-gray-50">
                        <td className="px-3 py-2 font-mono">{m.sku_canal}</td>
                        <td className="px-3 py-2">
                          <CanalBadge canal={m.canal} />
                        </td>
                        <td className="px-3 py-2 font-mono text-gray-500">
                          {m.id_anuncio ?? "—"}
                        </td>
                        <td className="px-3 py-2 font-mono font-semibold text-blue-700">
                          {m.sku_base}
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
