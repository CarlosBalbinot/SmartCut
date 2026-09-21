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

async function requestBlob(path) {
  const res = await apiFetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    const json = await res.json().catch(() => ({}));
    throw new Error(json.error || json.detail || `Erro ${res.status}`);
  }
  return res.blob();
}

export const getPedidosVenda = (tipo) =>
  request(`/pedidos-venda/${tipo ? `?tipo=${tipo}` : ""}`);

export const createPedidoVenda = (payload) =>
  request("/pedidos-venda/", { method: "POST", body: JSON.stringify(payload) });

export const getPedidoVenda = (id) => request(`/pedidos-venda/${id}`);

export const updatePedidoVenda = (id, payload) =>
  request(`/pedidos-venda/${id}`, { method: "PATCH", body: JSON.stringify(payload) });

export const updateStatusPedidoVenda = (id, status) =>
  request(`/pedidos-venda/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) });

export const deletePedidoVenda = (id) =>
  request(`/pedidos-venda/${id}`, { method: "DELETE" });

export const addItemPedidoVenda = (id, payload) =>
  request(`/pedidos-venda/${id}/itens`, { method: "POST", body: JSON.stringify(payload) });

export const updateItemPedidoVenda = (id, itemId, payload) =>
  request(`/pedidos-venda/${id}/itens/${itemId}`, { method: "PATCH", body: JSON.stringify(payload) });

export const removeItemPedidoVenda = (id, itemId) =>
  request(`/pedidos-venda/${id}/itens/${itemId}`, { method: "DELETE" });

export const getProximoNumeroPedidoVenda = (tipo = "venda") =>
  request(`/pedidos-venda/proximo-numero?tipo=${tipo}`);

export const gerarEncaixePedidoVenda = (id) =>
  request(`/pedidos-venda/${id}/gerar-encaixe`, { method: "POST" });

export const getPdfPedidoVenda = (id) => requestBlob(`/pedidos-venda/${id}/pdf-pedido`);

export const getPdfCortePedidoVenda = (id) => requestBlob(`/pedidos-venda/${id}/pdf-corte`);
