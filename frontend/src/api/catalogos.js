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

async function requestForm(path, formData) {
  const res = await apiFetch(`${BASE_URL}${path}`, { method: "POST", body: formData });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(json.error || json.detail || `Erro ${res.status}`);
  }
  return json.data;
}

// ── Catálogos de vendedor (PDF de catálogo por tabela) ───────────────────────

export const getCatalogos = () => request("/catalogos/");

export const createCatalogo = (formData) => requestForm("/catalogos/", formData);

export const getCatalogosVendedores = (catId) => request(`/catalogos/${catId}/vendedores`);

export const addVendedorCatalogo = (catId, vendedorId) =>
  request(`/catalogos/${catId}/vendedores`, {
    method: "POST",
    body: JSON.stringify({ vendedor_id: vendedorId }),
  });

export const removerVendedorCatalogo = (catId, vendedorId) =>
  request(`/catalogos/${catId}/vendedores/${vendedorId}`, { method: "DELETE" });
