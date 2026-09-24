# ── SmartCut frontend — DOCKERFILE DE PRODUÇÃO (item 3.2) ────────────────────
# Build estático (Vite) servido pelo nginx, que faz o proxy reverso de /api
# para o backend. Para desenvolvimento use o Dockerfile.dev.

# Estágio 1 — build
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
RUN npm run build

# Estágio 2 — servido pelo nginx
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]