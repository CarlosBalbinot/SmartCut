import { API_BASE } from '../services/config';
import { apiFetch } from '../services/api';
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

export const getClientes = (busca = "", tipo = "") => {
  const params = new URLSearchParams();
  if (busca) params.set("busca", busca);
  if (tipo) params.set("tipo", tipo);
  const qs = params.toString();
  return request(`/clientes/${qs ? `?${qs}` : ""}`);
};

export const getCliente = (id) => request(`/clientes/${id}`);

export const createCliente = (payload) =>
  request("/clientes/", { method: "POST", body: JSON.stringify(payload) });

export const updateCliente = (id, payload) =>
  request(`/clientes/${id}`, { method: "PUT", body: JSON.stringify(payload) });

export const deleteCliente = (id) =>
  request(`/clientes/${id}`, { method: "DELETE" });

export const getClienteByCnpj = async (cnpj) => {
  const res = await apiFetch(`${BASE_URL}/clientes/cnpj/${cnpj}`, {
    headers: { "Content-Type": "application/json" },
  });
  if (res.status === 404) return null;
  const json = await res.json();
  if (!res.ok) throw new Error(json.error || json.detail || `Erro ${res.status}`);
  return json.data;
};
