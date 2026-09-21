import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter, useLocation } from "react-router-dom";
import App from "./App";
import AppVendedor from "./AppVendedor";
import { ToastProvider } from "./contexts/ToastContext";
import { LogoProvider } from "./contexts/LogoContext";
import { AuthProvider } from "./auth/AuthContext";
import "./index.css";

function Root() {
  const location = useLocation();
  if (location.pathname === "/vendedor" || location.pathname.startsWith("/vendedor/")) {
    return <AppVendedor />;
  }
  return (
    <AuthProvider>
      <ToastProvider>
        <LogoProvider>
          <App />
        </LogoProvider>
      </ToastProvider>
    </AuthProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <HashRouter>
      <Root />
    </HashRouter>
  </React.StrictMode>
);
