import { API_BASE } from "../services/config";
import { apiFetch } from "../services/api";

const BASE_URL = `${API_BASE}/api/v1`;

async function request(path, options = {}) {
  const res = await apiFetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(json.error || json.detail || `Erro ${res.status}`);
  }
  return json.data;
}

// ── Configuração de precificação ─────────────────────────────────────────────

export const getConfigPrecificacao = () => request("/configuracao-precificacao/");

export const updateConfigPrecificacao = (payload) =>
  request("/configuracao-precificacao/", { method: "PATCH", body: JSON.stringify(payload) });

export const getCustosFixos = () => request("/configuracao-custos-fixos/");

export const updateCustosFixos = (payload) =>
  request("/configuracao-custos-fixos/", { method: "PATCH", body: JSON.stringify(payload) });

// ── Precificações por grupo de molde ─────────────────────────────────────────

export const getPrecificacoes = (grupoId) =>
  request(`/precificacoes/${grupoId ? `?grupo_id=${grupoId}` : ""}`);

export const createPrecificacao = (payload) =>
  request("/precificacoes/", { method: "POST", body: JSON.stringify(payload) });

export const updatePrecificacao = (id, payload) =>
  request(`/precificacoes/${id}`, { method: "PATCH", body: JSON.stringify(payload) });

export const deletePrecificacao = (id) => request(`/precificacoes/${id}`, { method: "DELETE" });

export const calcularPrecificacao = (grupoId) => request(`/precificacoes/${grupoId}/calcular`);
