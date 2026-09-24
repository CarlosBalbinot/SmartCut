import { API_BASE } from "../services/config";
import { apiFetch } from "../services/api";
const BASE_URL = `${API_BASE}/api/financeiro`;

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

async function requestForm(path, formData) {
  const res = await apiFetch(`${BASE_URL}${path}`, { method: "POST", body: formData });
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

async function requestBlob(path) {
  const res = await apiFetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    const json = await res.json().catch(() => ({}));
    throw new Error(json.error || json.detail || `Erro ${res.status}`);
  }
  return res.blob();
}

// ── Contas Bancárias ──────────────────────────────────────────────────────────

export const getContasBancarias = () => request("/contas-bancarias");

export const createContaBancaria = (dados) =>
  request("/contas-bancarias", { method: "POST", body: JSON.stringify(dados) });

export const updateContaBancaria = (id, dados) =>
  request(`/contas-bancarias/${id}`, { method: "PUT", body: JSON.stringify(dados) });

export const deleteContaBancaria = (id) => request(`/contas-bancarias/${id}`, { method: "DELETE" });

// ── Saldo ─────────────────────────────────────────────────────────────────────

export const getSaldoContas = (mes, ano) => request(`/saldo-contas?mes=${mes}&ano=${ano}`);

export const upsertSaldoInicial = (dados) =>
  request("/saldo-inicial", { method: "POST", body: JSON.stringify(dados) });

// ── Transferências entre contas ────────────────────────────────────────────────

export const createTransferencia = (dados) =>
  request("/transferencias", { method: "POST", body: JSON.stringify(dados) });

export const getTransferencias = (mes, ano) => request(`/transferencias?mes=${mes}&ano=${ano}`);

// ── Lançamentos ───────────────────────────────────────────────────────────────

export const getLancamentos = (mes, ano, tipo) => {
  const params = new URLSearchParams();
  if (mes != null) params.set("mes", mes);
  if (ano != null) params.set("ano", ano);
  if (tipo) params.set("tipo", tipo);
  const qs = params.toString();
  return request(`/lancamentos${qs ? `?${qs}` : ""}`);
};

export const createLancamento = (dados) =>
  request("/lancamentos", { method: "POST", body: JSON.stringify(dados) });

export const updateLancamento = (id, dados) =>
  request(`/lancamentos/${id}`, { method: "PUT", body: JSON.stringify(dados) });

export const deleteLancamento = (id) => request(`/lancamentos/${id}`, { method: "DELETE" });

export const confirmarPagamento = (id, contaId, dataPagamento) =>
  request(`/lancamentos/${id}/confirmar-pagamento`, {
    method: "POST",
    body: JSON.stringify({ conta_bancaria_id: contaId, data_pagamento: dataPagamento }),
  });

// ── Compras ───────────────────────────────────────────────────────────────────

export const getCompras = () => request("/compras");

export const createCompra = (dados) =>
  request("/compras", { method: "POST", body: JSON.stringify(dados) });

export const getCompra = (id) => request(`/compras/${id}`);

export const updateCompra = (id, dados) =>
  request(`/compras/${id}`, { method: "PUT", body: JSON.stringify(dados) });

export const deleteCompra = (id) => request(`/compras/${id}`, { method: "DELETE" });

export const importarXmlCompra = (arquivo) => {
  const fd = new FormData();
  fd.append("arquivo", arquivo);
  return requestForm("/compras/importar-xml", fd);
};

export const importarLoteCompras = (arquivos) => {
  const fd = new FormData();
  arquivos.forEach((arquivo) => fd.append("arquivos", arquivo));
  return requestForm("/compras/importar-lote", fd);
};

export const importarCompraFinal = (dados) =>
  request("/compras/importar", { method: "POST", body: JSON.stringify(dados) });

// ── Vendas Financeiras ────────────────────────────────────────────────────────

export const getVendasFinanceiras = () => request("/vendas-financeiras");

export const createVendaFinanceira = (dados) =>
  request("/vendas-financeiras", { method: "POST", body: JSON.stringify(dados) });

export const getVendaFinanceira = (id) => request(`/vendas-financeiras/${id}`);

export const updateVendaFinanceira = (id, dados) =>
  request(`/vendas-financeiras/${id}`, { method: "PUT", body: JSON.stringify(dados) });

export const deleteVendaFinanceira = (id) =>
  request(`/vendas-financeiras/${id}`, { method: "DELETE" });

export const importarXmlVenda = (arquivo) => {
  const fd = new FormData();
  fd.append("arquivo", arquivo);
  return requestForm("/vendas-financeiras/importar-xml", fd);
};

export const importarLoteVendas = (arquivos) => {
  const fd = new FormData();
  arquivos.forEach((arquivo) => fd.append("arquivos", arquivo));
  return requestForm("/vendas-financeiras/importar-lote", fd);
};

export const importarVendaFinal = (dados) =>
  request("/vendas-financeiras/importar", { method: "POST", body: JSON.stringify(dados) });

// ── DANFE Simplificada ───────────────────────────────────────────────────────

export const gerarDanfeSimplificada = async (arquivoXml) => {
  const formData = new FormData();
  formData.append("arquivo", arquivoXml);

  const response = await apiFetch(`${API_BASE}/api/financeiro/danfe-simplificada`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) throw new Error("Erro ao gerar DANFE");

  const blob = await response.blob();
  return blob;
};

// ── Anexos ────────────────────────────────────────────────────────────────────

export const uploadAnexo = (lancamentoId, arquivo, tipo) => {
  const fd = new FormData();
  fd.append("arquivo", arquivo);
  fd.append("tipo", tipo);
  return requestForm(`/lancamentos/${lancamentoId}/anexos`, fd);
};

export const getAnexos = (lancamentoId) => request(`/lancamentos/${lancamentoId}/anexos`);

export const downloadAnexo = (anexoId) => requestBlob(`/anexos/${anexoId}/download`);

export const deleteAnexo = (anexoId) => request(`/anexos/${anexoId}`, { method: "DELETE" });

// ── Projeção ──────────────────────────────────────────────────────────────────

export const getProjecao = (mesInicio, anoInicio, meses = 3) =>
  request(`/projecao?mes_inicio=${mesInicio}&ano_inicio=${anoInicio}&meses=${meses}`);

// ── Metas ─────────────────────────────────────────────────────────────────────

export const getMetas = (ano) => request(`/metas${ano != null ? `?ano=${ano}` : ""}`);

export const createMeta = (dados) =>
  request("/metas", { method: "POST", body: JSON.stringify(dados) });

export const updateMeta = (id, dados) =>
  request(`/metas/${id}`, { method: "PUT", body: JSON.stringify(dados) });

// ── Contabilidade ─────────────────────────────────────────────────────────────

export const getContabilidade = (mes, ano) => request(`/contabilidade?mes=${mes}&ano=${ano}`);

async function requestBlobPost(path, body) {
  const res = await apiFetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const json = await res.json().catch(() => ({}));
    throw new Error(json.error || json.detail || `Erro ${res.status}`);
  }
  return res.blob();
}

export const gerarPacoteContabil = (mes, ano) =>
  requestBlobPost("/contabilidade/gerar-pacote", { mes, ano });

export const gerarResumoInternoContabil = (mes, ano) =>
  requestBlobPost("/contabilidade/resumo-interno", { mes, ano });

// ── Métricas (dashboard) ─────────────────────────────────────────────────────

export const getMetricasCompras = (dataInicio, dataFim) => {
  const params = new URLSearchParams();
  if (dataInicio) params.set("data_inicio", dataInicio);
  if (dataFim) params.set("data_fim", dataFim);
  const qs = params.toString();
  return request(`/metricas-compras${qs ? `?${qs}` : ""}`);
};

export const getMetricasResultado = () => request("/metricas-resultado");
