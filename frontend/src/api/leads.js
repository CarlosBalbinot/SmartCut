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

// ── Leads de vendedor ────────────────────────────────────────────────────────

export const getLeads = () => request("/leads/");

export const createLead = (payload) =>
  request("/leads/", { method: "POST", body: JSON.stringify(payload) });

export const deleteLead = (id) => request(`/leads/${id}`, { method: "DELETE" });
