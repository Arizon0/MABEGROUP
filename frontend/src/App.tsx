import { Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api/client";
import { getUser, isAuthenticated } from "./auth";
import { ComprasPage } from "./pages/ComprasPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EstoquePage } from "./pages/EstoquePage";
import { FinanceiroPage } from "./pages/FinanceiroPage";
import { FornecedoresPage } from "./pages/FornecedoresPage";
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

function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <>{children}</>;
}

function Layout({ children }: { children: React.ReactNode }) {
  const user = getUser();
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="flex flex-wrap items-center gap-2 border-b border-gray-200 bg-white px-6 py-3">
        <span className="mr-4 font-bold text-gray-900">ERP Multicanal</span>
        <NavItem to="/" label="Dashboard" />
        <NavItem to="/sku-map" label="Mapa de SKUs" />
        <NavItem to="/produtos" label="Produtos" />
        <NavItem to="/fornecedores" label="Fornecedores" />
        <NavItem to="/estoque" label="Estoque" />
        <NavItem to="/compras" label="Compras" />
        <NavItem to="/financeiro" label="Financeiro" />
        <NavItem to="/relatorios" label="Relatórios" />
        <div className="ml-auto flex items-center gap-3">
          {user && (
            <span className="text-sm text-gray-500">{user.nome || user.email}</span>
          )}
          <button
            type="button"
            onClick={() => api.logout()}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100"
          >
            Sair
          </button>
        </div>
      </nav>
      {children}
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <Layout>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
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
          </RequireAuth>
        }
      />
    </Routes>
  );
}
