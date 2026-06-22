import { Routes, Route, Navigate } from "react-router-dom";
import LoginVendedorPage from "./pages/vendedor/LoginVendedorPage";
import DashboardVendedorPage from "./pages/vendedor/DashboardVendedorPage";
import CatalogosPage from "./pages/vendedor/CatalogosPage";
import PedidosVendedorPage from "./pages/vendedor/PedidosVendedorPage";
import LeadsPage from "./pages/vendedor/LeadsPage";

function ProtectedRoute({ children }) {
  const token = localStorage.getItem("smartcut_vendedor_token");
  if (!token) return <Navigate to="/vendedor/login" replace />;
  return children;
}

export default function AppVendedor() {
  return (
    <Routes>
      <Route path="/vendedor/login" element={<LoginVendedorPage />} />
      <Route
        path="/vendedor/dashboard"
        element={<ProtectedRoute><DashboardVendedorPage /></ProtectedRoute>}
      />
      <Route
        path="/vendedor/catalogos"
        element={<ProtectedRoute><CatalogosPage /></ProtectedRoute>}
      />
      <Route
        path="/vendedor/pedidos"
        element={<ProtectedRoute><PedidosVendedorPage /></ProtectedRoute>}
      />
      <Route
        path="/vendedor/leads"
        element={<ProtectedRoute><LeadsPage /></ProtectedRoute>}
      />
      <Route path="/vendedor" element={<Navigate to="/vendedor/dashboard" replace />} />
      <Route path="/vendedor/*" element={<Navigate to="/vendedor/login" replace />} />
    </Routes>
  );
}
