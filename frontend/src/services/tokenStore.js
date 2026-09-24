// Armazenamento do token de autenticação (item 1.4).
//
// O token JWT NÃO fica mais em localStorage:
// - Navegador (dev via Vite / implantação web): o backend emite cookie
//   HttpOnly na resposta do login — scripts da página não conseguem ler o
//   token; nada é persistido aqui.
// - Electron: token criptografado via safeStorage (IPC token-set/get/clear,
//   preload → main process), em arquivo no userData com escopo por sistema
//   (admin / vendedor). O renderer só obtém o valor sob demanda via IPC.

const electron = typeof window !== "undefined" ? window.electronAPI : undefined;

export const tokenStore = {
  /** Retorna o token do escopo (admin|vendedor) ou null quando não há. */
  async obter(escopo = "admin") {
    if (electron?.getToken) return electron.getToken(escopo);
    return null;
  },

  /** Salva o token (somente Electron). No navegador o cookie já foi emitido. */
  async salvar(token, escopo = "admin") {
    if (electron?.setToken) return electron.setToken(token, escopo);
    return null;
  },

  /** Remove o token persistido (Electron). No navegador o cookie é limpo no
   * logout pelo backend. */
  async limpar(escopo = "admin") {
    if (electron?.clearToken) return electron.clearToken(escopo);
    return null;
  },
};
