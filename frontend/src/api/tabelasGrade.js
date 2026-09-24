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

export const listar = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.situacao) qs.set("situacao", params.situacao);
  const query = qs.toString();
  return request(`/tabelas-grade/${query ? `?${query}` : ""}`);
};

export const buscarPorId = (id) => request(`/tabelas-grade/${id}`);

export const criar = (dados) =>
  request("/tabelas-grade/", { method: "POST", body: JSON.stringify(dados) });

export const atualizar = (id, dados) =>
  request(`/tabelas-grade/${id}`, { method: "PUT", body: JSON.stringify(dados) });

export const excluir = (id) => request(`/tabelas-grade/${id}`, { method: "DELETE" });

export const listarItens = (tabelaId) => request(`/tabelas-grade/${tabelaId}/itens/`);

export const criarItem = (tabelaId, dados) =>
  request(`/tabelas-grade/${tabelaId}/itens/`, { method: "POST", body: JSON.stringify(dados) });

export const atualizarItem = (tabelaId, itemId, dados) =>
  request(`/tabelas-grade/${tabelaId}/itens/${itemId}`, {
    method: "PUT",
    body: JSON.stringify(dados),
  });

export const excluirItem = (tabelaId, itemId) =>
  request(`/tabelas-grade/${tabelaId}/itens/${itemId}`, { method: "DELETE" });
