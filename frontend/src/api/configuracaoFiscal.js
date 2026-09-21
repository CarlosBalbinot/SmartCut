import { API_BASE } from '../services/config';
import { apiFetch } from '../services/api';
const BASE_URL = `${API_BASE}/api/v1/configuracao-empresa`;

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

export const getFiscal = () => request("/fiscal");

export const updateFiscal = (dados) =>
  request("/fiscal", { method: "PATCH", body: JSON.stringify(dados) });

export const testarCertificado = (certificado_path, certificado_senha) =>
  request("/fiscal/testar-certificado", {
    method: "POST",
    body: JSON.stringify({ certificado_path, certificado_senha }),
  });
