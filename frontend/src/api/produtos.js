import { API_BASE } from "../services/config";
import { apiFetch, erroDaResposta } from "../services/api";
const BASE_URL = `${API_BASE}/api/v1`;

async function request(path, options = {}) {
  const res = await apiFetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const json = await res.json();
  if (!res.ok) {
    throw erroDaResposta(res, json);
  }
  return json.data;
}

// ── Produtos ────────────────────────────────────────────────────────────

export const produtosApi = {
  listar: (filtros = {}) => {
    const params = new URLSearchParams();
    if (filtros.status) params.set("status_produto", filtros.status);
    if (filtros.grupoId) params.set("grupo_id", filtros.grupoId);
    if (filtros.excluirPais) params.set("excluir_pais", "true");
    const qs = params.toString();
    return request(`/produtos/${qs ? `?${qs}` : ""}`);
  },
  obter: (id) => request(`/produtos/${id}`),
  criar: (payload) => request("/produtos/", { method: "POST", body: JSON.stringify(payload) }),
  atualizar: (id, payload) =>
    request(`/produtos/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deletar: (id) => request(`/produtos/${id}`, { method: "DELETE" }),
  buscaPedido: (q) => request(`/produtos/busca-pedido?q=${encodeURIComponent(q)}`),
  gradePedido: (produtoPaiId) => request(`/produtos/${produtoPaiId}/grade-pedido`),
};

// ── Grupos de Produto ───────────────────────────────────────────────────

export const gruposProdutoApi = {
  listar: (situacao) => request(`/grupos-produto/${situacao ? `?situacao=${situacao}` : ""}`),
  criar: (payload) =>
    request("/grupos-produto/", { method: "POST", body: JSON.stringify(payload) }),
  atualizar: (id, payload) =>
    request(`/grupos-produto/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deletar: (id) => request(`/grupos-produto/${id}`, { method: "DELETE" }),
};

// ── Linhas / Colunas de Grade ────────────────────────────────────────────
