const BASE_URL = "/api/v1";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
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
  const res = await fetch(`${BASE_URL}${path}`, { method: "POST", body: formData });
  const json = await res.json();
  if (!res.ok) {
    throw new Error(json.error || json.detail || `Erro ${res.status}`);
  }
  return json.data;
}

async function requestBlob(path) {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    const json = await res.json().catch(() => ({}));
    throw new Error(json.error || json.detail || `Erro ${res.status}`);
  }
  return res.blob();
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
  obter: (id) => request(`/grupos-molde/${id}`),
  importar: (payload) =>
    request("/grupos-molde/importar", { method: "POST", body: JSON.stringify(payload) }),
  renomear: (id, payload) =>
    request(`/grupos-molde/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deletar: (id) => request(`/grupos-molde/${id}`, { method: "DELETE" }),
};

export const precificacoesApi = {
  getConfig: () => request("/configuracao-empresa/"),
  updateConfig: (payload) =>
    request("/configuracao-empresa/", { method: "PATCH", body: JSON.stringify(payload) }),
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
