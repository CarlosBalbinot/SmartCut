import { API_BASE } from "../services/config";
import { apiFetch } from "../services/api";

const BASE_URL = `${API_BASE}/api/v1/ordens-corte`;

// Erros levam o status HTTP (err.status) — o assistente mostra a mensagem
// da API em 409 (pendências, OC desatualizada) e trata 404 como "sem OC".
async function request(path, options = {}) {
  const res = await apiFetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(json.error || json.detail || `Erro ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return json.data;
}

// ── Ordem de Corte ───────────────────────────────────────────────────────────

export const criarOrdemCorte = (pedidoId) => request(`/pedido/${pedidoId}`, { method: "POST" });

export const getOrdemCorte = (id) => request(`/${id}`);

export const listarOrdensCorte = ({ status, pedidoId } = {}) => {
  const qs = new URLSearchParams();
  if (status) qs.set("status", status);
  if (pedidoId) qs.set("pedido_id", pedidoId);
  const q = qs.toString();
  return request(`/${q ? `?${q}` : ""}`);
};

// Resumo da OC ativa (não cancelada) do pedido, ou null. Usa a listagem
// (sempre 200) em vez de GET /pedido/{id}, que responde 404 quando o pedido
// não tem OC e sujaria o console a cada pedido aberto.
export const getOrdemCorteDoPedido = async (pedidoId) =>
  (await listarOrdensCorte({ pedidoId })).find((oc) => oc.status !== "CANCELADA") ?? null;

// escolhas: [{ produto_pai_id, cor, lote_id }] — lote_id null limpa a escolha.
export const definirTecidosOrdemCorte = (id, escolhas) =>
  request(`/${id}/tecidos`, { method: "PUT", body: JSON.stringify(escolhas) });

// payload: { modo_camadas?, comprimento_max_cm?, qualidade?, observacoes? }
// qualidade: RAPIDO | EQUILIBRADO | MAXIMO (tempo do motor v2).
export const atualizarOrdemCorte = (id, payload) =>
  request(`/${id}`, { method: "PUT", body: JSON.stringify(payload) });

export const atualizarOrdemCorteDoPedido = (id) =>
  request(`/${id}/atualizar-do-pedido`, { method: "POST" });

export const cancelarOrdemCorte = (id) => request(`/${id}/cancelar`, { method: "POST" });

// RASCUNHO com encaixes → ENVIADA (trava tecidos, modo e encaixes).
export const enviarOrdemCorte = (id) => request(`/${id}/enviar`, { method: "POST" });

// ── Produção (OC6b) ───────────────────────────────────────────────────────────

// ENVIADA → RASCUNHO: libera a edição dos tecidos (a reserva do lote é solta).
export const voltarOrdemCorteParaRascunho = (id) =>
  request(`/${id}/voltar-rascunho`, { method: "POST" });

// ENVIADA → EM_CORTE. `cortador` é opcional aqui: quem manda a OC para a
// máquina não é necessariamente quem assina o corte, então o nome fica
// obrigatório só na conclusão.
export const iniciarOrdemCorte = (id, cortador) =>
  request(`/${id}/iniciar`, {
    method: "POST",
    body: JSON.stringify({ cortador: cortador || null }),
  });

// EM_CORTE → CONCLUIDA: baixa de cada lote o peso real, tudo numa transação só.
// `consumos`: [{ lote_id, kg_real, sobra_kg }] — kg_real/sobra_kg opcionais;
// sem kg_real o lote consome o peso planejado pela OC.
export const concluirOrdemCorte = (id, { cortador, consumos = [], observacao } = {}) =>
  request(`/${id}/concluir`, {
    method: "POST",
    body: JSON.stringify({
      cortador,
      consumos,
      observacao: observacao || null,
    }),
  });

// CONCLUIDA → EM_CORTE: estorna o consumo da OC e devolve o peso aos lotes.
export const reabrirOrdemCorte = (id, { quem, observacao } = {}) =>
  request(`/${id}/reabrir`, {
    method: "POST",
    body: JSON.stringify({ quem, observacao: observacao || null }),
  });

export const simularOrdemCorte = (id, modo) =>
  request(`/${id}/simular${modo ? `?modo=${modo}` : ""}`);

// ── Geração de encaixes em segundo plano (M2a) ───────────────────────────────
//
// gerar-encaixes responde 202 { job_id } — o resultado sai em GET /job, que a
// tela consulta (ProgressoEncaixe). Estado do job: { job_id, status (FILA,
// RODANDO, CONCLUIDO, ERRO, CANCELADO), fase, mesa_atual, total_mesas,
// aproveitamento_parcial, iniciado_em, erro, resultado }.

export const gerarEncaixesOrdemCorte = (id) => request(`/${id}/gerar-encaixes`, { method: "POST" });

// Estado do job atual (ou do último) da OC; null se não houve nenhum desde
// que o backend subiu (a API responde 404).
export const getJobOrdemCorte = (id) =>
  request(`/${id}/job`).catch((e) => {
    if (e.status === 404) return null;
    throw e;
  });

// Cancela a geração — os encaixes anteriores da OC ficam como estavam.
export const cancelarJobOrdemCorte = (id) => request(`/${id}/job/cancelar`, { method: "POST" });

// Alerta de mesa maior (oc.sugestao_mesa): aplicar troca o comprimento máximo
// e já dispara a nova geração (202 { job_id, ordem_corte }); descartar
// esconde a sugestão até a próxima geração.
export const aplicarSugestaoMesa = (id) =>
  request(`/${id}/aplicar-sugestao-mesa`, { method: "POST" });

export const descartarSugestaoMesa = (id) =>
  request(`/${id}/descartar-sugestao-mesa`, { method: "POST" });

// Configurações > Produção: { motor_encaixe, comprimento_max_mesa_cm,
// alerta_economia_pct } — exige permissão de ver configurações.
export const getConfigProducao = () => request("/configuracao-producao");

// Lotes que podem ser escolhidos (sem arquivados/esgotados), com modelo,
// cor, largura, gramatura e peso disponível.
//
// Traz também `reservado_kg` (peso travado por outras OCs ENVIADA/EM_CORTE)
// e `livre_kg` (disponível menos a reserva — o que dá para planejar agora).
// `ocId` deixa a própria OC de fora da reserva: a tela que edita os tecidos
// de uma OC já enviada precisa do que sobraria para ela, não do que ela
// mesma travou.
export const getLotesDisponiveis = (ocId) =>
  request(`/lotes-disponiveis${ocId ? `?oc_id=${ocId}` : ""}`);
