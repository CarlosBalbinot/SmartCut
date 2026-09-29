const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getVersion: () => ipcRenderer.invoke('get-version'),
  platform: process.platform,
  // Em dev (NODE_ENV=development): string vazia — Vite proxy cuida do /api
  // Em produção (app empacotado): URL absoluta do backend local
  apiUrl: process.env.NODE_ENV === 'development' ? '' : 'http://127.0.0.1:8000',
  getComprasPath: () => ipcRenderer.invoke('get-compras-path'),
  openComprasFolder: () => ipcRenderer.invoke('open-compras-folder'),
  openPdfBlob: (base64, filename) => ipcRenderer.invoke('open-pdf-blob', base64, filename),
  // Item 4.1: diálogo nativo para escolher o caminho do certificado digital.
  selecionarCertificado: () => ipcRenderer.invoke('selecionar-certificado'),
  // Token de sessão criptografado via safeStorage (item 1.4): o token jamais
  // fica em localStorage — apenas IPC com o main process tem acesso ao arquivo.
  setToken: (token, escopo) => ipcRenderer.invoke('token-set', token, escopo),
  getToken: (escopo) => ipcRenderer.invoke('token-get', escopo),
  clearToken: (escopo) => ipcRenderer.invoke('token-clear', escopo),
});

// RL2: relatórios configuráveis (modelos da pasta relatorios/). gerarPdf
// busca o HTML no backend, gera o PDF e abre no visualizador do sistema;
// resolve { ok, caminho } ou { ok: false, status, erro, modelo }.
contextBridge.exposeInMainWorld('smartcut', {
  relatorios: {
    gerarPdf: (codigo, id, variante) => ipcRenderer.invoke('relatorio:gerar-pdf', codigo, id, variante),
  },
});
