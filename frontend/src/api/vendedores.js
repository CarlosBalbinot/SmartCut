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

export const getVendedores = (busca = "", status = "") => {
  const params = new URLSearchParams();
  if (busca) params.set("busca", busca);
  if (status) params.set("status", status);
  const qs = params.toString();
  return request(`/vendedores/${qs ? `?${qs}` : ""}`);
};

export const getVendedor = (id) => request(`/vendedores/${id}`);

export const createVendedor = (payload) =>
  request("/vendedores/", { method: "POST", body: JSON.stringify(payload) });

export const updateVendedor = (id, payload) =>
  request(`/vendedores/${id}`, { method: "PATCH", body: JSON.stringify(payload) });

export const deleteVendedor = (id) =>
  request(`/vendedores/${id}`, { method: "DELETE" });

export const getDashboardVendedor = (id) => request(`/vendedores/${id}/dashboard`);

export const getCredenciaisVendedor = (id) => request(`/vendedores/${id}/credenciais`);

export const setCredenciaisVendedor = (id, payload) =>
  request(`/vendedores/${id}/credenciais`, { method: "POST", body: JSON.stringify(payload) });

export const getMetasVendedor = (id) => request(`/vendedores/${id}/metas`);

export const updateMetasVendedor = (id, payload) =>
  request(`/vendedores/${id}/metas`, { method: "PATCH", body: JSON.stringify(payload) });

// Comissão por tabela de preço (tem prioridade sobre comissao_padrao_pct).
// PUT é upsert em lote [{tabela_preco_id, comissao_pct}] e devolve a
// lista completa atualizada.
export const getComissoesVendedor = (id) => request(`/vendedores/${id}/comissoes`);

export const salvarComissoesVendedor = (id, linhas) =>
  request(`/vendedores/${id}/comissoes`, { method: "PUT", body: JSON.stringify(linhas) });

export const removerComissaoVendedor = (id, comissaoId) =>
  request(`/vendedores/${id}/comissoes/${comissaoId}`, { method: "DELETE" });
