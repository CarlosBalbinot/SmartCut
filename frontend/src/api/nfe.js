import { API_BASE } from "../services/config";
import { apiFetch } from "../services/api";
const BASE_URL = `${API_BASE}/api/v1/nfe`;

async function request(path, options = {}) {
  const res = await apiFetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const json = await res.json();
  if (!res.ok) {
    const detail = json.detail;
    const msg = Array.isArray(detail)
      ? detail[0]?.msg || JSON.stringify(detail)
      : detail || json.error || `Erro ${res.status}`;
    throw new Error(msg);
  }
  return json.data;
}

async function requestBlob(path) {
  const res = await apiFetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    const json = await res.json().catch(() => ({}));
    throw new Error(json.detail || json.error || `Erro ${res.status}`);
  }
  return res.blob();
}

export const listar = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status_filtro", params.status);
  if (params.serie) qs.set("serie", params.serie);
  if (params.mes) qs.set("mes", params.mes);
  const s = qs.toString();
  return request(`/${s ? `?${s}` : ""}`);
};

export const buscarPorId = (id) => request(`/${id}`);

export const criar = (dados) => request("/", { method: "POST", body: JSON.stringify(dados) });

export const transmitir = (id) => request(`/${id}/transmitir`, { method: "POST" });

export const cancelar = (id, justificativa) =>
  request(`/${id}/cancelar`, { method: "POST", body: JSON.stringify({ justificativa }) });

export const getDanfe = (id) => requestBlob(`/${id}/danfe`);

export const cartaCorrecao = (id, correcao) =>
  request(`/${id}/carta-correcao`, { method: "POST", body: JSON.stringify({ correcao }) });
