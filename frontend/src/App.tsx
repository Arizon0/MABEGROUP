import { useEffect, useState } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import {
  encerrarSessao,
  observarSessao,
  tokenAtual,
  usuarioAtual,
} from "./api/sessao";
import { AnaliseVendasPage } from "./pages/AnaliseVendasPage";
import { ComprasPage } from "./pages/ComprasPage";
import { ContaPage } from "./pages/ContaPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DrePage } from "./pages/DrePage";
import { EstoquePage } from "./pages/EstoquePage";
import { FinanceiroPage } from "./pages/FinanceiroPage";
import { FornecedoresPage } from "./pages/FornecedoresPage";
import { ImportarPage } from "./pages/ImportarPage";
import { LoginPage } from "./pages/LoginPage";
import { ProdutosPage } from "./pages/ProdutosPage";
import { RelatoriosPage } from "./pages/RelatoriosPage";
import { SkuMapPage } from "./pages/SkuMapPage";

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `rounded px-3 py-1.5 text-sm font-medium ${
          isActive ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100"
        }`
      }
    >
      {label}
    </NavLink>
  );
}

function Layout({ children }: { children: React.ReactNode }) {
  const usuario = usuarioAtual();
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="flex flex-wrap items-center gap-2 border-b border-gray-200 bg-white px-6 py-3">
        <span className="mr-4 font-bold text-gray-900">ERP Multicanal</span>
        <NavItem to="/" label="Dashboard" />
        <NavItem to="/analise-vendas" label="Análise de Vendas" />
        <NavItem to="/dre" label="DRE" />
        <NavItem to="/importar" label="Importar" />
        <NavItem to="/sku-map" label="Mapa de SKUs" />
        <NavItem to="/produtos" label="Produtos" />
        <NavItem to="/fornecedores" label="Fornecedores" />
        <NavItem to="/estoque" label="Estoque" />
        <NavItem to="/compras" label="Compras" />
        <NavItem to="/financeiro" label="Financeiro" />
        <NavItem to="/relatorios" label="Relatórios" />
        <div className="ml-auto flex items-center gap-3">
          <NavLink
            to="/conta"
            className="text-sm text-gray-600 hover:underline"
            title="Minha conta"
          >
            {usuario?.nome || usuario?.email || "Conta"}
          </NavLink>
          <button
            type="button"
            onClick={() => encerrarSessao()}
            className="rounded border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Sair
          </button>
        </div>
      </nav>
      {children}
    </div>
  );
}

/** Segue a sessão guardada no navegador e re-renderiza quando ela muda.
 *
 * O `observarSessao` é o que faz a aplicação cair no login sozinha quando a
 * API responde 401 e o cliente descarta o token no meio de uma requisição.
 */
function useSessao(): boolean {
  const [autenticado, setAutenticado] = useState(() => tokenAtual() !== null);
  useEffect(() => observarSessao(() => setAutenticado(tokenAtual() !== null)), []);
  return autenticado;
}

export default function App() {
  const autenticado = useSessao();

  // Sem sessão nenhuma rota interna é montada — a proteção de verdade está no
  // servidor, mas não adianta renderizar telas que só saberiam mostrar erro.
  if (!autenticado) return <LoginPage />;

  return (
    <Routes>
      <Route
        path="/*"
        element={
          <Layout>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/analise-vendas" element={<AnaliseVendasPage />} />
              <Route path="/dre" element={<DrePage />} />
              <Route path="/importar" element={<ImportarPage />} />
              <Route path="/sku-map" element={<SkuMapPage />} />
              <Route path="/produtos" element={<ProdutosPage />} />
              <Route path="/fornecedores" element={<FornecedoresPage />} />
              <Route path="/estoque" element={<EstoquePage />} />
              <Route path="/compras" element={<ComprasPage />} />
              <Route path="/financeiro" element={<FinanceiroPage />} />
              <Route path="/relatorios" element={<RelatoriosPage />} />
              <Route path="/conta" element={<ContaPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Layout>
        }
      />
    </Routes>
  );
}
