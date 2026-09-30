import { API_BASE } from "../services/config";
import { apiFetch } from "../services/api";
const BASE_URL = `${API_BASE}/api/v1`;

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

async function requestForm(path, formData) {
  const res = await apiFetch(`${BASE_URL}${path}`, { method: "POST", body: formData });
  const json = await res.json();
  if (!res.ok) {
    throw new Error(json.error || json.detail || `Erro ${res.status}`);
  }
  return json.data;
}

// ── Grupos de molde ───────────────────────────────────────────────────

export const getGrupos = () => request("/grupos-molde/");

export const buscarGrupos = (busca) => request(`/grupos-molde/?busca=${encodeURIComponent(busca)}`);

export const getGrupo = (id) => request(`/grupos-molde/${id}`);

export const importarGrupoMolde = (payload) =>
  request("/grupos-molde/importar", { method: "POST", body: JSON.stringify(payload) });

export const renomearGrupo = (id, payload) =>
  request(`/grupos-molde/${id}`, { method: "PATCH", body: JSON.stringify(payload) });

export const deleteGrupo = (id) => request(`/grupos-molde/${id}`, { method: "DELETE" });

// ── Moldes ────────────────────────────────────────────────────────────

export const getMoldes = () => request("/moldes/");

export const getMolde = (id) => request(`/moldes/${id}`);

export const previewMolde = (formData) => requestForm("/moldes/preview", formData);

export const bulkImportarMoldes = (payload) =>
  request("/moldes/bulk", { method: "POST", body: JSON.stringify(payload) });

export const updateMolde = (id, payload) =>
  request(`/moldes/${id}`, { method: "PATCH", body: JSON.stringify(payload) });

export const deleteMolde = (id) => request(`/moldes/${id}`, { method: "DELETE" });

// Simetria da peça no eixo do fio (mesma medida do decisor do enfesto):
// { geometrias: [geometria_json...], sentido_fio, rotacao_base } →
// { simetrica: bool | null, desvio_cm, tolerancia_cm }.
export const simetriaMolde = (payload) =>
  request("/moldes/simetria", { method: "POST", body: JSON.stringify(payload) });

// ── Produtos (para vínculo com o grupo de molde) ────────────────────────

export const buscarProdutos = (termo) => request(`/produtos/?busca=${encodeURIComponent(termo)}`);
