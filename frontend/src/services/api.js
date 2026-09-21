import { API_BASE } from './config';
const BASE_URL = `${API_BASE}/api/v1`;

export const ADMIN_TOKEN_KEY = 'smartcut_admin_token';

// Substituto direto de fetch() para chamadas autenticadas do sistema admin:
// injeta o Bearer token salvo no login e, se a resposta vier 401 (token
// ausente/expirado/inválido), limpa a sessão e redireciona para /login.
export async function apiFetch(url, options = {}) {
  const token = localStorage.getItem(ADMIN_TOKEN_KEY);
  const headers = { ...options.headers };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    window.location.hash = '/login';
  }

  return res;
}

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

async function requestBlob(path) {
  const res = await apiFetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    const json = await res.json().catch(() => ({}));
    throw new Error(json.error || json.detail || `Erro ${res.status}`);
  }
  return res.blob();
}

async function requestFormMethod(path, formData, method = "POST") {
  const res = await apiFetch(`${BASE_URL}${path}`, { method, body: formData });
  const json = await res.json();
  if (!res.ok) throw new Error(json.error || json.detail || `Erro ${res.status}`);
  return json.data;
}

// ── Nova hierarquia: Modelo → Cor → Lote ─────────────────────────────

export const modelosApi = {
  listar: () => request("/modelos-tecido/"),
  obter: (id) => request(`/modelos-tecido/${id}`),
  criar: (payload) => request("/modelos-tecido/", { method: "POST", body: JSON.stringify(payload) }),
  atualizar: (id, payload) =>
    request(`/modelos-tecido/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deletar: (id) => request(`/modelos-tecido/${id}`, { method: "DELETE" }),
  listarCores: (id) => request(`/modelos-tecido/${id}/cores`),
  criarCor: (id, payload) =>
    request(`/modelos-tecido/${id}/cores`, { method: "POST", body: JSON.stringify(payload) }),
};

export const coresApi = {
  obter: (id) => request(`/cores-tecido/${id}`),
  atualizar: (id, payload) =>
    request(`/cores-tecido/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deletar: (id) => request(`/cores-tecido/${id}`, { method: "DELETE" }),
  listarLotes: (id) => request(`/cores-tecido/${id}/lotes`),
  criarLote: (id, payload) =>
    request(`/cores-tecido/${id}/lotes`, { method: "POST", body: JSON.stringify(payload) }),
  recomendar: (id) => request(`/cores-tecido/${id}/recomendar-lote`),
};

export const lotesApi = {
  obter: (id) => request(`/lotes-tecido/${id}`),
  atualizar: (id, payload) =>
    request(`/lotes-tecido/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  arquivar: (id) => request(`/lotes-tecido/${id}/arquivar`, { method: "POST" }),
  listarAlertas: () => request("/lotes-tecido/alertas"),
  listarHistorico: () => request("/lotes-tecido/historico"),
  proximoCodigo: () => request("/lotes-tecido/proximo-codigo").then((d) => d.codigo),
};

// ── Legado ────────────────────────────────────────────────────────────

export const tecidosApi = {
  listar: () => request("/tecidos/"),
  obter: (id) => request(`/tecidos/${id}`),
  criar: (payload) => request("/tecidos/", { method: "POST", body: JSON.stringify(payload) }),
  atualizar: (id, payload) =>
    request(`/tecidos/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deletar: (id) => request(`/tecidos/${id}`, { method: "DELETE" }),
};

export const pedidosApi = {
  listar: () => request("/pedidos/"),
  obter: (id) => request(`/pedidos/${id}`),
  proximoNumero: () => request("/pedidos/proximo-numero").then((d) => d.numero),
  criar: (payload) => request("/pedidos/", { method: "POST", body: JSON.stringify(payload) }),
  atualizar: (id, payload) =>
    request(`/pedidos/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  alterarStatus: (id, status) =>
    request(`/pedidos/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  deletar: (id) => request(`/pedidos/${id}`, { method: "DELETE" }),
  duplicar: (id) => request(`/pedidos/${id}/duplicar`, { method: "POST" }),
  // Tecidos: agora usa lote_id; pt_id é o id do registro pedido_tecidos
  adicionarTecido: (id, lote_id) =>
    request(`/pedidos/${id}/tecidos`, { method: "POST", body: JSON.stringify({ lote_id }) }),
  removerTecido: (id, pt_id) =>
    request(`/pedidos/${id}/tecidos/${pt_id}`, { method: "DELETE" }),
  adicionarGrupoPecas: (id, payload) =>
    request(`/pedidos/${id}/pecas`, { method: "POST", body: JSON.stringify(payload) }),
  removerGrupoPecas: (id, grupo_id, tamanho) =>
    request(`/pedidos/${id}/pecas/${grupo_id}/${tamanho}`, { method: "DELETE" }),
  resumoCorte: (id) => request(`/pedidos/${id}/resumo-corte`),
  relatorioPdf: (id) => requestBlob(`/pedidos/${id}/relatorio-pdf`),
  metricas: (dataInicio, dataFim) => {
    const params = new URLSearchParams();
    if (dataInicio) params.set("data_inicio", dataInicio);
    if (dataFim) params.set("data_fim", dataFim);
    const qs = params.toString();
    return request(`/pedidos/metricas${qs ? `?${qs}` : ""}`);
  },
};

export const moldesApi = {
  listar: () => request("/moldes/"),
  obter: (id) => request(`/moldes/${id}`),
  preview: (formData) => requestForm("/moldes/preview", formData),
  bulkImportar: (payload) =>
    request("/moldes/bulk", { method: "POST", body: JSON.stringify(payload) }),
  atualizar: (id, payload) =>
    request(`/moldes/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deletar: (id) => request(`/moldes/${id}`, { method: "DELETE" }),
};

export const gruposApi = {
  listar: () => request("/grupos-molde/"),
  buscar: (search) => request(`/grupos-molde/?search=${encodeURIComponent(search)}`),
  obter: (id) => request(`/grupos-molde/${id}`),
  importar: (payload) =>
    request("/grupos-molde/importar", { method: "POST", body: JSON.stringify(payload) }),
  renomear: (id, payload) =>
    request(`/grupos-molde/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deletar: (id) => request(`/grupos-molde/${id}`, { method: "DELETE" }),
};

export const precificacoesApi = {
  getConfig: () => request("/configuracao-precificacao/"),
  updateConfig: (payload) =>
    request("/configuracao-precificacao/", { method: "PATCH", body: JSON.stringify(payload) }),
  getCustos: () => request("/configuracao-custos-fixos/"),
  updateCustos: (payload) =>
    request("/configuracao-custos-fixos/", { method: "PATCH", body: JSON.stringify(payload) }),
  listar: (grupoId) =>
    request(`/precificacoes/${grupoId ? `?grupo_id=${grupoId}` : ""}`),
  upsert: (payload) =>
    request("/precificacoes/", { method: "POST", body: JSON.stringify(payload) }),
  atualizar: (id, payload) =>
    request(`/precificacoes/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deletar: (id) =>
    request(`/precificacoes/${id}`, { method: "DELETE" }),
  calcular: (grupoId) => request(`/precificacoes/${grupoId}/calcular`),
};

export const encaixesApi = {
  listar: (pedidoId) =>
    request(`/encaixes/${pedidoId ? `?pedido_id=${pedidoId}` : ""}`),
  obter: (id) => request(`/encaixes/${id}`),
  gerar: (payload) =>
    request("/encaixes/", { method: "POST", body: JSON.stringify(payload) }),
  gerarAutomatico: (pedidoId) =>
    request(`/encaixes/gerar/${pedidoId}`, { method: "POST" }),
  deletar: (id) => request(`/encaixes/${id}`, { method: "DELETE" }),
  relatorio: (id) => request(`/encaixes/${id}/relatorio`),
  pdf: (pedidoId) => requestBlob(`/encaixes/${pedidoId}/pdf`),
};

export const configuracaoEmpresaApi = {
  get: () => request("/configuracao-empresa/"),
  update: (payload) =>
    request("/configuracao-empresa/", { method: "PATCH", body: JSON.stringify(payload) }),
  uploadLogo: (formData) => requestFormMethod("/configuracao-empresa/logo", formData, "PATCH"),
};

export const tabelasPrecoApi = {
  list: () => request("/tabelas-preco/"),
  create: (payload) =>
    request("/tabelas-preco/", { method: "POST", body: JSON.stringify(payload) }),
  update: (id, payload) =>
    request(`/tabelas-preco/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  remove: (id) => request(`/tabelas-preco/${id}`, { method: "DELETE" }),
  listItens: (id) => request(`/tabelas-preco/${id}/itens`),
  addItem: (id, payload) =>
    request(`/tabelas-preco/${id}/itens`, { method: "POST", body: JSON.stringify(payload) }),
  removeItem: (id, grupoId) =>
    request(`/tabelas-preco/${id}/itens/${grupoId}`, { method: "DELETE" }),
};

export const referenciasApi = {
  list: () => request("/referencias/"),
  create: (payload) =>
    request("/referencias/", { method: "POST", body: JSON.stringify(payload) }),
  update: (id, payload) =>
    request(`/referencias/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  getPrecos: (id) => request(`/referencias/${id}/precos`),
  setPreco: (id, payload) =>
    request(`/referencias/${id}/precos`, { method: "POST", body: JSON.stringify(payload) }),
};

export const vendedoresApi = {
  list: (busca = "", status = "") => {
    const params = new URLSearchParams();
    if (busca) params.set("busca", busca);
    if (status) params.set("status", status);
    const qs = params.toString();
    return request(`/vendedores/${qs ? `?${qs}` : ""}`);
  },
  create: (payload) =>
    request("/vendedores/", { method: "POST", body: JSON.stringify(payload) }),
  update: (id, payload) =>
    request(`/vendedores/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  remove: (id) => request(`/vendedores/${id}`, { method: "DELETE" }),
  getDashboard: (id) => request(`/vendedores/${id}/dashboard`),
  getCredenciais: (id) => request(`/vendedores/${id}/credenciais`),
  setCredenciais: (id, payload) =>
    request(`/vendedores/${id}/credenciais`, { method: "POST", body: JSON.stringify(payload) }),
  getMetas: (id) => request(`/vendedores/${id}/metas`),
  updateMetas: (id, payload) =>
    request(`/vendedores/${id}/metas`, { method: "PATCH", body: JSON.stringify(payload) }),
};

export const catalogosApi = {
  list: () => request("/catalogos/"),
  create: (formData) => requestForm("/catalogos/", formData),
  remove: (id) => request(`/catalogos/${id}`, { method: "DELETE" }),
  listVendedores: (catId) => request(`/catalogos/${catId}/vendedores`),
  addVendedor: (catId, vendedorId) =>
    request(`/catalogos/${catId}/vendedores`, { method: "POST", body: JSON.stringify({ vendedor_id: vendedorId }) }),
  removeVendedor: (catId, vendedorId) =>
    request(`/catalogos/${catId}/vendedores/${vendedorId}`, { method: "DELETE" }),
};

export const leadsApi = {
  list: () => request("/leads/"),
  create: (payload) =>
    request("/leads/", { method: "POST", body: JSON.stringify(payload) }),
  remove: (id) => request(`/leads/${id}`, { method: "DELETE" }),
};

export const clientesApi = {
  listar: (busca = "", tipo = "") => {
    const params = new URLSearchParams();
    if (busca) params.set("busca", busca);
    if (tipo) params.set("tipo", tipo);
    const qs = params.toString();
    return request(`/clientes/${qs ? `?${qs}` : ""}`);
  },
  criar: (payload) =>
    request("/clientes/", { method: "POST", body: JSON.stringify(payload) }),
  obter: (id) => request(`/clientes/${id}`),
  atualizar: (id, payload) =>
    request(`/clientes/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deletar: (id) => request(`/clientes/${id}`, { method: "DELETE" }),
  buscarCnpj: async (cnpj) => {
    const res = await apiFetch(`${API_BASE}/api/v1/clientes/cnpj/${cnpj}`, {
      headers: { "Content-Type": "application/json" },
    });
    if (res.status === 404) return null;
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || json.detail || `Erro ${res.status}`);
    return json.data;
  },
};

// pedidosVendaApi foi removido daqui — unificado em src/api/pedidos.js
// (que já usa apiFetch, autenticado; este arquivo usa fetch() puro).
