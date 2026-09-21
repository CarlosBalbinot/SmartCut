import { API_BASE } from '../services/config';
import { apiFetch } from '../services/api';
const BASE_URL = `${API_BASE}/api/v1/tes`;

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

export const listar = () => request("/");

export const buscarPorId = (id) => request(`/${id}`);

export const criar = (dados) =>
  request("/", { method: "POST", body: JSON.stringify(dados) });

export const atualizar = (id, dados) =>
  request(`/${id}`, { method: "PUT", body: JSON.stringify(dados) });

export const excluir = (id) => request(`/${id}`, { method: "DELETE" });
