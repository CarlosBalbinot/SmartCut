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

export const transportadorasApi = {
  listar: (busca = "", bloqueado = "") => {
    const params = new URLSearchParams();
    if (busca) params.set("busca", busca);
    if (bloqueado !== "") params.set("bloqueado", bloqueado);
    const qs = params.toString();
    return request(`/transportadoras/${qs ? `?${qs}` : ""}`);
  },
  obter: (id) => request(`/transportadoras/${id}`),
  criar: (payload) =>
    request("/transportadoras/", { method: "POST", body: JSON.stringify(payload) }),
  atualizar: (id, payload) =>
    request(`/transportadoras/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deletar: (id) => request(`/transportadoras/${id}`, { method: "DELETE" }),
};
