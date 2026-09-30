import { API_BASE } from "../services/config";
import { apiFetch } from "../services/api";

const BASE_URL = `${API_BASE}/api/v1`;

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

async function requestBlob(path) {
  const res = await apiFetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    const json = await res.json().catch(() => ({}));
    throw new Error(json.error || json.detail || `Erro ${res.status}`);
  }
  return res.blob();
}

// ── Encaixes ─────────────────────────────────────────────────────────────────

export const getEncaixes = (pedidoId) =>
  request(`/encaixes/${pedidoId ? `?pedido_id=${pedidoId}` : ""}`);

export const getEncaixe = (id) => request(`/encaixes/${id}`);

export const gerarEncaixe = (payload) =>
  request("/encaixes/", { method: "POST", body: JSON.stringify(payload) });

// ── Encaixe Rápido em segundo plano (M2d) ────────────────────────────────────
//
// A geração roda como job no backend (o motor v2 leva minutos): o POST
// devolve 202 { job_id } e o resultado sai no GET .../job — mesmo formato do
// job da Ordem de Corte, acompanhado pelo ProgressoEncaixe. O resultado do
// job é { encaixes, avisos, decisoes (decisão do enfesto por lote), motor_usado }.

const rapidoQs = ({ comprimentoMaxCm, qualidade, tipoEnfesto, modoCamadas } = {}) => {
  const qs = new URLSearchParams();
  if (comprimentoMaxCm) qs.set("comprimento_max_cm", comprimentoMaxCm);
  if (qualidade) qs.set("qualidade", qualidade);
  if (tipoEnfesto) qs.set("tipo_enfesto", tipoEnfesto);
  if (modoCamadas) qs.set("modo_camadas", modoCamadas);
  const q = qs.toString();
  return q ? `?${q}` : "";
};

// comprimentoMaxCm: limite da mesa (padrão do backend 150 cm) — risco maior
// é dividido em mesas. qualidade: AUTOMATICO (padrão) | RAPIDO | EQUILIBRADO
// | MAXIMO. tipoEnfesto (AUTOMATICO | MESMA_FACE | FACE_A_FACE) e
// modoCamadas (AUTOMATICO | SEM_SOBRA | MENOS_ENFESTOS): "Avançado" —
// AUTOMATICO (padrão) deixa o sistema decidir.
export const gerarEncaixeRapido = (pedidoId, opcoes) =>
  request(`/ordens-corte/encaixe-rapido/${pedidoId}${rapidoQs(opcoes)}`, { method: "POST" });

// Valida as peças antes de gerar (sem enfileirar nada):
// { problemas: [...], avisos: [...] } — problema bloqueia a geração.
export const validarEncaixeRapido = (pedidoId, opcoes) =>
  request(`/ordens-corte/encaixe-rapido/${pedidoId}/validar${rapidoQs(opcoes)}`);

// Estado do job do pedido; null se não houve nenhum desde que o backend subiu.
export const getJobEncaixeRapido = (pedidoId) =>
  request(`/ordens-corte/encaixe-rapido/${pedidoId}/job`).catch((e) => {
    if (e.status === 404) return null;
    throw e;
  });

export const cancelarJobEncaixeRapido = (pedidoId) =>
  request(`/ordens-corte/encaixe-rapido/${pedidoId}/job/cancelar`, { method: "POST" });

// Lê um Encaixe Rápido já gerado (somente leitura): devolve
// { config: { nome, tecidos, pecas, comprimento_max_cm, qualidade },
//   resultado: { pedido_id, encaixes, comprimento_max_cm, avisos } } — a tela
// reabre com ?id=<pedido_id> na URL e recarrega sem regenerar.
export const getEncaixeRapido = (pedidoId) => request(`/ordens-corte/encaixe-rapido/${pedidoId}`);

// Rota antiga: desde o M2d também só enfileira o job (202 { job_id }).
export const gerarEncaixeAutomatico = (pedidoId, comprimentoMaxCm) =>
  request(`/encaixes/gerar/${pedidoId}${rapidoQs({ comprimentoMaxCm })}`, { method: "POST" });

export const deleteEncaixe = (id) => request(`/encaixes/${id}`, { method: "DELETE" });

export const getRelatorioEncaixe = (id) => request(`/encaixes/${id}/relatorio`);

export const getPdfEncaixe = (pedidoId) => requestBlob(`/encaixes/${pedidoId}/pdf`);

// ── Configurações > Produção (mesa de corte) ─────────────────────────────────
// payload: { comprimento_max_mesa_cm, alerta_economia_pct }
// — o GET é getConfigProducao (api/ordensCorte). Exige configuracoes_editar.
export const atualizarConfigProducao = (payload) =>
  request("/ordens-corte/configuracao-producao", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
