import { API_BASE } from "../services/config";
import { apiFetch, erroDaResposta } from "../services/api";

const BASE_URL = `${API_BASE}/api/v1`;

async function request(path, options = {}) {
  const res = await apiFetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw erroDaResposta(res, json);
  }
  return json.data;
}

// ── Tabelas de preço ─────────────────────────────────────────────────────────

export const getTabelasPreco = () => request("/tabelas-preco/");

export const createTabelaPreco = (payload) =>
  request("/tabelas-preco/", { method: "POST", body: JSON.stringify(payload) });

export const updateTabelaPreco = (id, payload) =>
  request(`/tabelas-preco/${id}`, { method: "PATCH", body: JSON.stringify(payload) });

export const deleteTabelaPreco = (id) => request(`/tabelas-preco/${id}`, { method: "DELETE" });

// ── Itens (grupos de molde por tabela) ───────────────────────────────────────

export const getItensTabelaPreco = (id) => request(`/tabelas-preco/${id}/itens`);

export const addItemTabelaPreco = (id, payload) =>
  request(`/tabelas-preco/${id}/itens`, { method: "POST", body: JSON.stringify(payload) });

export const removeItemTabelaPreco = (id, grupoId) =>
  request(`/tabelas-preco/${id}/itens/${grupoId}`, { method: "DELETE" });

// ── Preços por produto pai / exceção por SKU (precos_tabela_produto).
//    PUT é upsert em lote e devolve a lista completa atualizada. ──────────────

export const getPrecosProdutoTabela = (id) => request(`/tabelas-preco/${id}/precos-produto`);

export const salvarPrecosProdutoTabela = (id, linhas) =>
  request(`/tabelas-preco/${id}/precos-produto`, { method: "PUT", body: JSON.stringify(linhas) });

export const removerPrecoProdutoTabela = (id, precoId) =>
  request(`/tabelas-preco/${id}/precos-produto/${precoId}`, { method: "DELETE" });
