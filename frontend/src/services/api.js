import { tokenStore } from "./tokenStore";

// Arquivo de utilitários compartilhados da camada de API do frontend.
// Todos os métodos por domínio vivem em src/api/*.js (um módulo por domínio),
// que importam daqui apenas `apiFetch` e `mensagemErro` — item 7.1:
// nenhum grupo de API fica mais definido neste arquivo, garantindo que a
// busca por um endpoint revele a definição num único lugar.

// Substituto direto de fetch() para chamadas autenticadas do sistema admin:
// injeta o Bearer token quando houver (Electron → safeStorage; no navegador a
// autenticação vem do cookie HttpOnly emitido pelo backend) e, se a resposta
// vier 401 (token ausente/expirado/inválido), limpa a sessão e redireciona
// para /login.
export async function apiFetch(url, options = {}) {
  const token = await tokenStore.obter("admin");
  const headers = { ...options.headers };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(url, {
    ...options,
    headers,
    credentials: options.credentials ?? "include",
  });

  if (res.status === 401) {
    await tokenStore.limpar("admin");
    window.location.hash = "/login";
  }

  return res;
}

// Texto de erro exibível ao usuário. Formato do backend (F0 passo 5a):
// {"error": {codigo, params, mensagem}, "detail": mensagem}. A mensagem em
// português passa direto (inclusive em 5xx de regra, como o motor de
// encaixe); erro interno, lista de validação do pydantic, 5xx sem o formato
// novo ou sem JSON e qualquer coisa com cara de erro de banco viram mensagem
// genérica — nunca mostrar erro técnico cru na tela. `fallback` (opcional)
// substitui a genérica quando o backend não mandou mensagem aproveitável.
const _ERRO_TECNICO =
  /sqlalchemy|sqlite|psycopg|integrityerror|operationalerror|traceback|\b(select|insert|update|delete)\b.+\b(from|into|set|where)\b/i;
const _MSG_GENERICA = "Não foi possível concluir a operação. Tente novamente.";

function _erroEstruturado(json) {
  const e = json?.error;
  return e && typeof e === "object" && !Array.isArray(e) ? e : null;
}

export function mensagemErro(json, status, fallback) {
  const estruturado = _erroEstruturado(json);
  let msg;
  if (estruturado) {
    if (estruturado.codigo === "ERRO_INTERNO") return fallback || _MSG_GENERICA;
    msg = estruturado.mensagem;
  } else {
    if (status >= 500) return fallback || _MSG_GENERICA;
    msg = json?.error || json?.detail;
  }
  if (Array.isArray(msg)) return "Dados inválidos. Verifique os campos.";
  if (typeof msg !== "string" || !msg.trim())
    return fallback || `Não foi possível concluir a operação (erro ${status}).`;
  if (_ERRO_TECNICO.test(msg))
    return "Não foi possível concluir a operação. Verifique os dados e tente novamente.";
  return msg;
}

// Error pronto para `throw` a partir de uma resposta não-ok: mensagem
// exibível (mensagemErro) mais `status`, `codigo` (ex.: "OC_STATUS_MUDOU";
// null se o backend não mandou) e `params` — a tela decide pelo código,
// não pelo texto. `json` é o corpo já lido ({} se não veio JSON);
// `fallback`: mensagem da tela para quando o backend não mandou nenhuma.
export function erroDaResposta(res, json, fallback) {
  const status = res?.status ?? 0;
  const estruturado = _erroEstruturado(json);
  const err = new Error(mensagemErro(json, status, fallback));
  err.status = status;
  err.codigo = estruturado?.codigo ?? null;
  err.params = estruturado?.params ?? {};
  return err;
}
