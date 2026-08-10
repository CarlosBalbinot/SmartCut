import { API_BASE } from '../services/config';
const BASE_URL = `${API_BASE}/api/financeiro`;

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
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
  const res = await fetch(`${BASE_URL}${path}`, { method: "POST", body: formData });
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
  const res = await fetch(`${BASE_URL}${path}`);
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

export const deleteContaBancaria = (id) =>
  request(`/contas-bancarias/${id}`, { method: "DELETE" });

// ── Saldo ─────────────────────────────────────────────────────────────────────

export const getSaldoContas = (mes, ano) =>
  request(`/saldo-contas?mes=${mes}&ano=${ano}`);

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

export const deleteLancamento = (id) =>
  request(`/lancamentos/${id}`, { method: "DELETE" });

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

export const deleteCompra = (id) =>
  request(`/compras/${id}`, { method: "DELETE" });

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

// ── Anexos ────────────────────────────────────────────────────────────────────

export const uploadAnexo = (lancamentoId, arquivo, tipo) => {
  const fd = new FormData();
  fd.append("arquivo", arquivo);
  fd.append("tipo", tipo);
  return requestForm(`/lancamentos/${lancamentoId}/anexos`, fd);
};

export const getAnexos = (lancamentoId) =>
  request(`/lancamentos/${lancamentoId}/anexos`);

export const downloadAnexo = (anexoId) =>
  requestBlob(`/anexos/${anexoId}/download`);

export const deleteAnexo = (anexoId) =>
  request(`/anexos/${anexoId}`, { method: "DELETE" });

// ── Projeção ──────────────────────────────────────────────────────────────────

export const getProjecao = (mesInicio, anoInicio, meses = 3) =>
  request(`/projecao?mes_inicio=${mesInicio}&ano_inicio=${anoInicio}&meses=${meses}`);

// ── Metas ─────────────────────────────────────────────────────────────────────

export const getMetas = (ano) =>
  request(`/metas${ano != null ? `?ano=${ano}` : ""}`);

export const createMeta = (dados) =>
  request("/metas", { method: "POST", body: JSON.stringify(dados) });

export const updateMeta = (id, dados) =>
  request(`/metas/${id}`, { method: "PUT", body: JSON.stringify(dados) });
