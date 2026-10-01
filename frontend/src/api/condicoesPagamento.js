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

export const listar = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.situacao) qs.set("situacao", params.situacao);
  const query = qs.toString();
  return request(`/condicoes-pagamento/${query ? `?${query}` : ""}`);
};

export const buscarPorId = (id) => request(`/condicoes-pagamento/${id}`);

export const criar = (dados) =>
  request("/condicoes-pagamento/", { method: "POST", body: JSON.stringify(dados) });

export const atualizar = (id, dados) =>
  request(`/condicoes-pagamento/${id}`, { method: "PUT", body: JSON.stringify(dados) });

export const excluir = (id) => request(`/condicoes-pagamento/${id}`, { method: "DELETE" });

export const simular = (dados) =>
  request("/condicoes-pagamento/simular", { method: "POST", body: JSON.stringify(dados) });
