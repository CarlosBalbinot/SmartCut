import { createContext, useCallback, useEffect, useState } from "react";
import { API_BASE } from "../services/config";
import { apiFetch, ADMIN_TOKEN_KEY } from "../services/api";

const AUTH_BASE = `${API_BASE}/api/v1/auth`;

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const salvo = localStorage.getItem(ADMIN_TOKEN_KEY);
    if (!salvo) {
      setLoading(false);
      return;
    }
    setToken(salvo);
    apiFetch(`${AUTH_BASE}/me`)
      .then(async (res) => {
        if (!res.ok) throw new Error("sessão inválida");
        const json = await res.json();
        setUsuario(json.data);
      })
      .catch(() => {
        localStorage.removeItem(ADMIN_TOKEN_KEY);
        setToken(null);
        setUsuario(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username, senha) => {
    const res = await fetch(`${AUTH_BASE}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, senha }),
    });
    const json = await res.json();
    if (!res.ok) {
      throw new Error(json.detail || json.error || "Não foi possível entrar.");
    }
    localStorage.setItem(ADMIN_TOKEN_KEY, json.data.token);
    setToken(json.data.token);
    setUsuario(json.data.usuario);
    return json.data.usuario;
  }, []);

  const logout = useCallback(() => {
    apiFetch(`${AUTH_BASE}/logout`, { method: "POST" }).catch(() => {});
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    setToken(null);
    setUsuario(null);
    window.location.hash = "/login";
  }, []);

  const atualizarMe = useCallback(async (payload) => {
    const res = await apiFetch(`${AUTH_BASE}/me`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const json = await res.json();
    if (!res.ok) {
      throw new Error(json.detail || json.error || "Não foi possível salvar.");
    }
    setUsuario(json.data);
    return json.data;
  }, []);

  const hasPermission = useCallback(
    (modulo, acao) => {
      if (!usuario) return false;
      if (usuario.is_admin) return true;
      return (usuario.permissoes || []).some(
        (p) => p.modulo === modulo && p.acao === acao
      );
    },
    [usuario]
  );

  return (
    <AuthContext.Provider value={{ usuario, token, loading, login, logout, hasPermission, atualizarMe }}>
      {children}
    </AuthContext.Provider>
  );
}
