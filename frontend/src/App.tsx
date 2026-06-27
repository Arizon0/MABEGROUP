import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { EstoquePage } from "./pages/EstoquePage";
import { FornecedoresPage } from "./pages/FornecedoresPage";
import { ProdutosPage } from "./pages/ProdutosPage";
import { SkuMapPage } from "./pages/SkuMapPage";

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
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

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="flex items-center gap-2 border-b border-gray-200 bg-white px-6 py-3">
        <span className="mr-4 font-bold text-gray-900">ERP Multicanal</span>
        <NavItem to="/sku-map" label="Mapa de SKUs" />
        <NavItem to="/produtos" label="Produtos" />
        <NavItem to="/fornecedores" label="Fornecedores" />
        <NavItem to="/estoque" label="Estoque" />
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to="/sku-map" replace />} />
        <Route path="/sku-map" element={<SkuMapPage />} />
        <Route path="/produtos" element={<ProdutosPage />} />
        <Route path="/fornecedores" element={<FornecedoresPage />} />
        <Route path="/estoque" element={<EstoquePage />} />
      </Routes>
    </div>
  );
}
