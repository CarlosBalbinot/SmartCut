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
    const detail = json.detail;
    const msg = Array.isArray(detail)
      ? detail[0]?.msg || JSON.stringify(detail)
      : detail || json.error || `Erro ${res.status}`;
    throw new Error(msg);
  }
  return json.data;
}

export const listarProdutos = (filtros = {}) => {
  const params = new URLSearchParams();
  if (filtros.grupoId) params.set("grupo_id", filtros.grupoId);
  const qs = params.toString();
  return request(`/produtos/${qs ? `?${qs}` : ""}`);
};

export const criarProdutoPai = (payload) =>
  request("/produtos/", { method: "POST", body: JSON.stringify(payload) });

export const atualizarProdutoPai = (id, payload) =>
  request(`/produtos/${id}`, { method: "PUT", body: JSON.stringify(payload) });

export const gerarSkus = (produtoId, combinacoes) =>
  request(`/produtos/${produtoId}/skus/gerar`, {
    method: "POST",
    body: JSON.stringify({ combinacoes }),
  });

export const sincronizarSkus = (produtoId, { combinacoes = [], removerSkuIds = [] }) =>
  request(`/produtos/${produtoId}/skus/sincronizar`, {
    method: "POST",
    body: JSON.stringify({ combinacoes, remover_sku_ids: removerSkuIds }),
  });

export const listarSkus = (produtoId) => request(`/produtos/${produtoId}/skus/`);

export const atualizarSku = (produtoId, skuId, payload) =>
  request(`/produtos/${produtoId}/skus/${skuId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

export const excluirSku = (produtoId, skuId) =>
  request(`/produtos/${produtoId}/skus/${skuId}`, { method: "DELETE" });
