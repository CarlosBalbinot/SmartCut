import { tokenStore } from './tokenStore';

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
  const token = await tokenStore.obter('admin');
  const headers = { ...options.headers };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(url, { ...options, headers, credentials: options.credentials ?? 'include' });

  if (res.status === 401) {
    await tokenStore.limpar('admin');
    window.location.hash = '/login';
  }

  return res;
}

// Texto de erro exibível ao usuário: o detail em português dos
// HTTPException passa direto; lista de validação do pydantic, resposta 5xx
// ou sem JSON e qualquer coisa com cara de erro de banco viram mensagem
// genérica — nunca mostrar erro técnico cru na tela.
const _ERRO_TECNICO = /sqlalchemy|sqlite|psycopg|integrityerror|operationalerror|traceback|\b(select|insert|update|delete)\b.+\b(from|into|set|where)\b/i;

export function mensagemErro(json, status) {
  const msg = json?.error || json?.detail;
  if (status >= 500) return "Não foi possível concluir a operação. Tente novamente.";
  if (Array.isArray(msg)) return "Dados inválidos. Verifique os campos.";
  if (typeof msg !== "string" || !msg.trim()) return `Não foi possível concluir a operação (erro ${status}).`;
  if (_ERRO_TECNICO.test(msg)) return "Não foi possível concluir a operação. Verifique os dados e tente novamente.";
  return msg;
}