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

export const obter = () => request("/configuracao-grade/");

export const atualizar = (dados) =>
  request("/configuracao-grade/", { method: "PATCH", body: JSON.stringify(dados) });

export const preview = (dados) =>
  request("/configuracao-grade/preview", { method: "POST", body: JSON.stringify(dados) });
