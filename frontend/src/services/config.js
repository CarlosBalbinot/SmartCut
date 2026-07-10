// API_BASE é injetado pelo preload do Electron antes de qualquer módulo carregar.
// Dev  → '' (Vite proxy transparentemente redireciona /api → localhost:8000)
// Prod → 'http://127.0.0.1:8000' (chamadas diretas ao backend local)
export const API_BASE = window.electronAPI?.apiUrl ?? '';
