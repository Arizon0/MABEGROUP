import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { ComprasPage } from "./pages/ComprasPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EstoquePage } from "./pages/EstoquePage";
import { FinanceiroPage } from "./pages/FinanceiroPage";
import { FornecedoresPage } from "./pages/FornecedoresPage";
import { ImportarPage } from "./pages/ImportarPage";
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
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="flex flex-wrap items-center gap-2 border-b border-gray-200 bg-white px-6 py-3">
        <span className="mr-4 font-bold text-gray-900">ERP Multicanal</span>
        <NavItem to="/" label="Dashboard" />
        <NavItem to="/importar" label="Importar" />
        <NavItem to="/sku-map" label="Mapa de SKUs" />
        <NavItem to="/produtos" label="Produtos" />
        <NavItem to="/fornecedores" label="Fornecedores" />
        <NavItem to="/estoque" label="Estoque" />
        <NavItem to="/compras" label="Compras" />
        <NavItem to="/financeiro" label="Financeiro" />
        <NavItem to="/relatorios" label="Relatórios" />
      </nav>
      {children}
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/*"
        element={
          <Layout>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/importar" element={<ImportarPage />} />
              <Route path="/sku-map" element={<SkuMapPage />} />
              <Route path="/produtos" element={<ProdutosPage />} />
              <Route path="/fornecedores" element={<FornecedoresPage />} />
              <Route path="/estoque" element={<EstoquePage />} />
              <Route path="/compras" element={<ComprasPage />} />
              <Route path="/financeiro" element={<FinanceiroPage />} />
              <Route path="/relatorios" element={<RelatoriosPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Layout>
        }
      />
    </Routes>
  );
}
