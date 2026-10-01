import { API_BASE } from "../services/config";
import { apiFetch, erroDaResposta } from "../services/api";
const BASE_URL = `${API_BASE}/api/v1`;

async function request(path, options = {}) {
  const res = await apiFetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const json = await res.json();
  if (!res.ok) {
    const err = erroDaResposta(res, json);
    // Salvar em lote (422): [{ item_id | ref_temp, campo, mensagem }] por item.
    err.erros = json.erros || null;
    throw err;
  }
  return json.data;
}

export const getPedidosVenda = (tipo) => request(`/pedidos-venda/${tipo ? `?tipo=${tipo}` : ""}`);

export const createPedidoVenda = (payload) =>
  request("/pedidos-venda/", { method: "POST", body: JSON.stringify(payload) });

export const getPedidoVenda = (id) => request(`/pedidos-venda/${id}`);

// "Salvar Pedido": cabeçalho + itens pendentes ({ ...cabeçalho, itens: lote })
// numa transação só — item inválido → 422 com err.erros e nada é gravado.
export const salvarPedidoVenda = (id, payload) =>
  request(`/pedidos-venda/${id}`, { method: "PUT", body: JSON.stringify(payload) });

export const updateStatusPedidoVenda = (id, status) =>
  request(`/pedidos-venda/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) });

export const addItemPedidoVenda = (id, payload) =>
  request(`/pedidos-venda/${id}/itens`, { method: "POST", body: JSON.stringify(payload) });

export const addItensBulkPedidoVenda = (id, itens) =>
  request(`/pedidos-venda/${id}/itens/bulk`, { method: "POST", body: JSON.stringify({ itens }) });

// "Salvar Itens": lote { criar, atualizar, remover } — tudo ou nada.
// Devolve o pedido completo (itens e totais recalculados).
export const salvarItensPedidoVenda = (id, lote) =>
  request(`/pedidos-venda/${id}/itens`, { method: "PUT", body: JSON.stringify(lote) });

export const getProximoNumeroPedidoVenda = (tipo = "venda") =>
  request(`/pedidos-venda/proximo-numero?tipo=${tipo}`);

// Reprecifica todos os itens pela tabela (inclusive preço manual).
// Devolve { pedido, sem_preco: [referências que mantiveram o preço] }.
export const aplicarTabelaPedidoVenda = (id, tabela_preco_id) =>
  request(`/pedidos-venda/${id}/aplicar-tabela`, {
    method: "POST",
    body: JSON.stringify({ tabela_preco_id }),
  });

// Prévia das parcelas (cálculo só no backend). Todos opcionais — o que não
// vier usa o gravado no pedido. primeiroVencimento "" = sem 1º vencimento;
// total = total local quando há itens/cabeçalho pendentes.
// Devolve [{ numero, total_parcelas, vencimento: "YYYY-MM-DD", valor }].
export const getParcelasPreviewPedidoVenda = (
  id,
  { primeiroVencimento, total, condicaoPagamentoId } = {}
) => {
  const params = new URLSearchParams();
  if (primeiroVencimento != null) params.set("primeiro_vencimento", primeiroVencimento);
  if (total != null) params.set("total", Number(total).toFixed(2));
  if (condicaoPagamentoId) params.set("condicao_pagamento_id", condicaoPagamentoId);
  const qs = params.toString();
  return request(`/pedidos-venda/${id}/parcelas-preview${qs ? `?${qs}` : ""}`);
};

// Métricas de vendas do dashboard executivo (PainelFinanceiro).
export const getMetricasPedidosVenda = (dataInicio, dataFim) => {
  const params = new URLSearchParams();
  if (dataInicio) params.set("data_inicio", dataInicio);
  if (dataFim) params.set("data_fim", dataFim);
  const qs = params.toString();
  return request(`/pedidos-venda/metricas${qs ? `?${qs}` : ""}`);
};
