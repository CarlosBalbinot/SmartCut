// Cliente HTTP do painel do vendedor (item 1.4).
//
// Substitui as cópias locais de `vendedorFetch`/`vendedorFetchRaw` que liam o
// token direto do localStorage. Agora o token vem de `tokenStore`:
// - Electron → safeStorage (via IPC);
// - Navegador → cookie HttpOnly emitido pelo backend (credentials: include);
// e em 401 a sessão é limpa e o usuário volta ao /vendedor/login.
import { API_BASE } from "./config";
import { tokenStore } from "./tokenStore";

const BASE_URL = `${API_BASE}/api/v1`;
const ESCOPO = "vendedor";

function extrairErro(json, status) {
  return json?.error || json?.detail || `Erro ${status}`;
}

async function request(path, options = {}, envelopeCompleto = false) {
  const token = await tokenStore.obter(ESCOPO);
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: options.credentials ?? "include",
  });

  const json = await res.json().catch(() => ({}));

  if (res.status === 401) {
    await tokenStore.limpar(ESCOPO);
    window.location.hash = "/vendedor/login";
    throw new Error(extrairErro(json, res.status));
  }
  if (!res.ok) throw new Error(extrairErro(json, res.status));

  return envelopeCompleto ? json : json.data;
}

/** Faz uma chamada autenticada e devolve apenas `json.data`. */
export function vendedorFetch(path, options = {}) {
  return request(path, options, false);
}

/** Igual ao vendedorFetch, mas devolve o envelope completo `{data, error}`. */
export function vendedorFetchRaw(path, options = {}) {
  return request(path, options, true);
}

/** Logout do painel: revoga o token no backend (jti) e limpa a sessão local. */
export async function logoutVendedor() {
  try {
    await vendedorFetchRaw("/vendedor/logout", { method: "POST" });
  } catch (_) {
    // Token já inválido/expirado — segue para limpeza local.
  }
  await tokenStore.limpar(ESCOPO);
  localStorage.removeItem("smartcut_vendedor_info");
}
