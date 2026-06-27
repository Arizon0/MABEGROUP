import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Produto } from "../types/skuMap";

interface Props {
  onSelecionar: (produto: Produto) => void;
  placeholder?: string;
}

/** Campo de busca para localizar um `sku_base` no cadastro de produtos. */
export function ProdutoBusca({ onSelecionar, placeholder }: Props) {
  const [termo, setTermo] = useState("");
  const [resultados, setResultados] = useState<Produto[]>([]);
  const [aberto, setAberto] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (termo.trim().length === 0) {
      setResultados([]);
      return;
    }
    timer.current = setTimeout(async () => {
      try {
        const produtos = await api.buscarProdutos(termo.trim());
        setResultados(produtos);
        setAberto(true);
      } catch {
        setResultados([]);
      }
    }, 250);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [termo]);

  return (
    <div className="relative">
      <input
        type="text"
        value={termo}
        onChange={(e) => setTermo(e.target.value)}
        onFocus={() => resultados.length && setAberto(true)}
        placeholder={placeholder ?? "Buscar SKU base ou nome do produto..."}
        className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
        aria-label="Buscar produto"
      />
      {aberto && resultados.length > 0 && (
        <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded border border-gray-200 bg-white shadow-lg">
          {resultados.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                className="flex w-full items-center justify-between px-3 py-1.5 text-left text-sm hover:bg-blue-50"
                onClick={() => {
                  onSelecionar(p);
                  setTermo("");
                  setResultados([]);
                  setAberto(false);
                }}
              >
                <span className="font-mono font-semibold text-gray-800">{p.sku_base}</span>
                <span className="ml-2 truncate text-gray-500">{p.nome}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
