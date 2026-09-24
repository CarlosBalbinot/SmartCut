// API_BASE é injetado pelo preload do Electron antes de qualquer módulo carregar.
// Dev  → '' (Vite proxy transparentemente redireciona /api → localhost:8000)
// Prod → 'http://127.0.0.1:8000' (chamadas diretas ao backend local)
export const API_BASE = window.electronAPI?.apiUrl ?? '';

// URLs relativas vindas do backend (ex.: logo_url) precisam do prefixo do
// backend: no navegador (dev) o Vite proxy resolve '/api'; no Electron a
// chamada é absoluta (http://127.0.0.1:8000), senão resolveria contra a
// origem app:// do frontend.
export function urlAbsoluta(url) {
  if (!url) return null;
  if (/^[a-z][a-z0-9+.-]*:/i.test(url)) return url; // já absoluta
  return `${API_BASE}${url.startsWith("/") ? url : `/${url}`}`;
}
