import { API_BASE } from "../services/config";
import { apiFetch, erroDaResposta } from "../services/api";
const BASE_URL = `${API_BASE}/api/v1/usuarios`;

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

export const usuariosApi = {
  listar: () => request("/"),
  obter: (id) => request(`/${id}`),
  criar: (payload) => request("/", { method: "POST", body: JSON.stringify(payload) }),
  atualizar: (id, payload) => request(`/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  substituirPermissoes: (id, permissoes) =>
    request(`/${id}/permissoes`, { method: "PUT", body: JSON.stringify({ permissoes }) }),
  desativar: (id) => request(`/${id}`, { method: "DELETE" }),
};
