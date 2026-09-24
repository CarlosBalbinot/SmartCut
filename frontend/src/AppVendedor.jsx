import { useEffect, useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import LoginVendedorPage from "./pages/vendedor/LoginVendedorPage";
import DashboardVendedorPage from "./pages/vendedor/DashboardVendedorPage";
import CatalogosPage from "./pages/vendedor/CatalogosPage";
import PedidosVendedorPage from "./pages/vendedor/PedidosVendedorPage";
import LeadsPage from "./pages/vendedor/LeadsPage";
import { vendedorFetch } from "./services/vendedorApi";

function ProtectedRoute({ children }) {
  const [autorizado, setAutorizado] = useState(null);

  // Item 1.4: o token não é mais lido de localStorage de forma síncrona.
  // Em qualquer modo (safeStorage no Electron ou cookie HttpOnly no navegador)
  // a sessão é validada com uma chamada autenticada; 401 redireciona para o
  // login do painel.
  useEffect(() => {
    let ativo = true;
    vendedorFetch("/vendedor/perfil")
      .then(() => ativo && setAutorizado(true))
      .catch(() => ativo && setAutorizado(false));
    return () => {
      ativo = false;
    };
  }, []);

  if (autorizado === null) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", fontFamily: "system-ui, sans-serif", color: "#6E6E73" }}>
        Carregando…
      </div>
    );
  }
  if (!autorizado) return <Navigate to="/vendedor/login" replace />;
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