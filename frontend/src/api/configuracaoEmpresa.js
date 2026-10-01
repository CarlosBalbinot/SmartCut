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

async function requestFormMethod(path, formData, method) {
  const res = await apiFetch(`${BASE_URL}${path}`, { method, body: formData });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw erroDaResposta(res, json);
  }
  return json.data;
}

// ── Configuração da empresa ───────────────────────────────────────────────────

export const getConfiguracaoEmpresa = () => request("/configuracao-empresa/");

export const updateConfiguracaoEmpresa = (payload) =>
  request("/configuracao-empresa/", { method: "PATCH", body: JSON.stringify(payload) });

export const uploadLogoEmpresa = (formData) =>
  requestFormMethod("/configuracao-empresa/logo", formData, "PATCH");
