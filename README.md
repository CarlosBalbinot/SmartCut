# SmartCut

Sistema de gestão para confecção: cadastros de tecidos, moldes e produtos,
pedidos de venda, **ordem de corte com encaixe automático** (motor spyrrow +
OR-Tools), ficha de corte, NF-e, financeiro e painel do vendedor. Aplicativo
desktop para Windows: Electron + React (frontend) + FastAPI (backend) + SQLite.

## Rodar em desenvolvimento

Requisitos: Python 3.12 e Node 22.

```bash
# Backend — http://localhost:8000/docs
cd backend
py -3.12 -m pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env
py -3.12 -m uvicorn main:app --reload

# Frontend — http://localhost:5173
cd frontend
npm install
npm run dev

# App desktop em modo dev (opcional, na raiz)
npm install
npm run electron-dev
```

No primeiro acesso o sistema pede o cadastro do administrador.

## Documentação

- [docs/SISTEMA.md](docs/SISTEMA.md) — como o sistema funciona (arquitetura,
  módulos, fluxos, motor de encaixe, relatórios, pasta de dados, instalação,
  backup).
- [docs/DESENVOLVIMENTO.md](docs/DESENVOLVIMENTO.md) — setup, testes,
  migrations, build do instalador e release.
- [docs/CLAUDE.md](docs/CLAUDE.md) — regras para agentes de código
  ([AGENTS.md](AGENTS.md) aponta para ele).
- [docs/historico/](docs/historico/) — especificações e planos antigos.
