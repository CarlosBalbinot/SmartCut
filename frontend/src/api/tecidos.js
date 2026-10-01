import { API_BASE } from "../services/config";
import { apiFetch } from "../services/api";
const BASE_URL = `${API_BASE}/api/v1`;

async function request(path, options = {}) {
  const res = await apiFetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const json = await res.json();
  if (!res.ok) {
    throw new Error(json.error || json.detail || `Erro ${res.status}`);
  }
  return json.data;
}

// ── Modelos ───────────────────────────────────────────────────────────

export const getModelos = () => request("/modelos-tecido/");

export const createModelo = (payload) =>
  request("/modelos-tecido/", { method: "POST", body: JSON.stringify(payload) });

export const updateModelo = (id, payload) =>
  request(`/modelos-tecido/${id}`, { method: "PATCH", body: JSON.stringify(payload) });

export const deleteModelo = (id) => request(`/modelos-tecido/${id}`, { method: "DELETE" });

export const getCoresDoModelo = (id) => request(`/modelos-tecido/${id}/cores`);

export const createCorDoModelo = (id, payload) =>
  request(`/modelos-tecido/${id}/cores`, { method: "POST", body: JSON.stringify(payload) });

// ── Cores ─────────────────────────────────────────────────────────────

export const updateCor = (id, payload) =>
  request(`/cores-tecido/${id}`, { method: "PATCH", body: JSON.stringify(payload) });

export const deleteCor = (id) => request(`/cores-tecido/${id}`, { method: "DELETE" });

export const getLotesDaCor = (id) => request(`/cores-tecido/${id}/lotes`);

export const createLoteDaCor = (id, payload) =>
  request(`/cores-tecido/${id}/lotes`, { method: "POST", body: JSON.stringify(payload) });

// ── Lotes ─────────────────────────────────────────────────────────────

export const arquivarLote = (id) => request(`/lotes-tecido/${id}/arquivar`, { method: "POST" });

export const getAlertasLotes = () => request("/lotes-tecido/alertas");

export const getHistoricoLotes = () => request("/lotes-tecido/historico");

export const getProximoCodigoLote = () =>
  request("/lotes-tecido/proximo-codigo").then((d) => d.codigo);
