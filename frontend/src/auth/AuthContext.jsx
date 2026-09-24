import { createContext, useCallback, useEffect, useState } from "react";
import { API_BASE } from "../services/config";
import { apiFetch } from "../services/api";
import { tokenStore } from "../services/tokenStore";

const AUTH_BASE = `${API_BASE}/api/v1/auth`;

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  // Item 1.4: o token não fica mais em localStorage. No Electron vem do
  // safeStorage; no navegador a sessão vem do cookie HttpOnly — como o cookie
  // não é legível por script, o carregamento inicial sempre valida via /me.
  useEffect(() => {
    tokenStore
      .obter("admin")
      .then((tok) => {
        if (tok) setToken(tok);
        return apiFetch(`${AUTH_BASE}/me`);
      })
      .then(async (res) => {
        if (!res.ok) throw new Error("sessão inválida");
        const json = await res.json();
        setUsuario(json.data);
      })
      .catch(() => {
        tokenStore.limpar("admin");
        setToken(null);
        setUsuario(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username, senha) => {
    const res = await fetch(`${AUTH_BASE}/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, senha }),
    });
    const json = await res.json();
    if (!res.ok) {
      throw new Error(json.detail || json.error || "Não foi possível entrar.");
    }
    // Item 1.4: Electron persiste via safeStorage; no navegador o cookie
    // HttpOnly já foi emitido pelo backend na resposta do login.
    await tokenStore.salvar(json.data.token, "admin");
    setToken(json.data.token);
    setUsuario(json.data.usuario);
    return json.data.usuario;
  }, []);

  const logout = useCallback(() => {
    apiFetch(`${AUTH_BASE}/logout`, { method: "POST" }).catch(() => {});
    tokenStore.limpar("admin");
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
