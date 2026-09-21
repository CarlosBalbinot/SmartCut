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
});
