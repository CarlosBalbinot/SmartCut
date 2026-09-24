import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// No DEV o @vitejs/plugin-react injeta um script inline (preamble do
// react-refresh) no index.html — a CSP estrita de produção (meta tag no
// index.html) quebraria o HMR. Este plugin (só no servidor de dev) troca a
// meta tag por uma versão compatível; o build de produção mantém a estrita.
const CSP_DEV = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "connect-src 'self' ws: http://127.0.0.1:8000",
  "font-src 'self' data:",
].join("; ");

export default defineConfig({
  base: './',
  plugins: [
    react(),
    {
      name: "csp-dev",
      apply: "serve",
      transformIndexHtml(html) {
        return html.replace(
          /<meta http-equiv="Content-Security-Policy"[^>]*\/?>/i,
          `<meta http-equiv="Content-Security-Policy" content="${CSP_DEV}" />`
        );
      },
    },
  ],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});