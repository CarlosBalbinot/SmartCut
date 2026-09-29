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

async function requestBlob(path) {
  const res = await apiFetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    const json = await res.json().catch(() => ({}));
    throw new Error(json.error || json.detail || `Erro ${res.status}`);
  }
  return res.blob();
}

// ── Encaixes ─────────────────────────────────────────────────────────────────

export const getEncaixes = (pedidoId) =>
  request(`/encaixes/${pedidoId ? `?pedido_id=${pedidoId}` : ""}`);

export const getEncaixe = (id) => request(`/encaixes/${id}`);

export const gerarEncaixe = (payload) =>
  request("/encaixes/", { method: "POST", body: JSON.stringify(payload) });

// comprimentoMaxCm: limite da mesa — risco maior é dividido em partes
// (sem ele, o backend usa 150 cm).
export const gerarEncaixeAutomatico = (pedidoId, comprimentoMaxCm) =>
  request(
    `/encaixes/gerar/${pedidoId}${comprimentoMaxCm ? `?comprimento_max_cm=${comprimentoMaxCm}` : ""}`,
    { method: "POST" }
  );

export const deleteEncaixe = (id) => request(`/encaixes/${id}`, { method: "DELETE" });

export const getRelatorioEncaixe = (id) => request(`/encaixes/${id}/relatorio`);

export const getPdfEncaixe = (pedidoId) => requestBlob(`/encaixes/${pedidoId}/pdf`);
