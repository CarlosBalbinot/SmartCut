import { API_BASE } from '../services/config';
import { apiFetch } from '../services/api';

const BASE_URL = `${API_BASE}/api/v1/dashboard`;

export async function getDashboardResumo() {
  const res = await apiFetch(`${BASE_URL}/resumo`);
  const json = await res.json();
  if (!res.ok) {
    throw new Error(json.detail || json.error || `Erro ${res.status}`);
  }
  return json.data;
}
