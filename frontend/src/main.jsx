import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, useLocation } from "react-router-dom";
import App from "./App";
import AppVendedor from "./AppVendedor";
import { ToastProvider } from "./contexts/ToastContext";
import { LogoProvider } from "./contexts/LogoContext";
import "./index.css";

function Root() {
  const location = useLocation();
  if (location.pathname.startsWith("/vendedor")) {
    return <AppVendedor />;
  }
  return (
    <ToastProvider>
      <LogoProvider>
        <App />
      </LogoProvider>
    </ToastProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Root />
    </BrowserRouter>
  </React.StrictMode>
);
