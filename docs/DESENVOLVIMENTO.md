# SmartCut — Desenvolvimento

Como montar o ambiente, rodar, testar e gerar o instalador. Para entender o
sistema em si, leia antes o [SISTEMA.md](SISTEMA.md).

---

## Setup

Requisitos: Windows, **Python 3.12** (sempre `py -3.12 -m ...`, nunca `python`
ou outra versão) e **Node 22**.

```bash
# Backend
cd backend
py -3.12 -m pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env          # ajuste SECRET_KEY (e CERT_SENHA_KEY para testar NF-e)

# Frontend
cd frontend
npm install

# Electron (raiz)
npm install
```

`backend/.env` é a fonte única de configuração do backend (lido por
`backend/config.py`; variável de ambiente do processo vence o arquivo).
Principais variáveis:

| Variável | Para quê |
|---|---|
| `DATABASE_URL` | Banco de dev, padrão `sqlite:///./smartcut.db` (`backend/smartcut.db`). |
| `SECRET_KEY` | Segredo JWT. Sem ele o backend gera um efêmero e as sessões caem a cada boot. Gere com `py -3.12 -c "import secrets; print(secrets.token_hex(32))"`. |
| `CERT_SENHA_KEY` | Chave que cifra a senha do certificado em dev (no app instalado o Electron cuida disso). Trocar a chave invalida as senhas gravadas. |
| `CERTIFICADO_DIR` | Pasta padrão do `.pfx`; vazio = `Certificados/` na raiz do projeto. |
| `BACKUP_DIR`, `BACKUP_MANTER`, `BACKUP_INTERVAL_SEC` | Backup automático (padrão: ao lado do .db, 30 cópias, 6 h). |
| `SMARTCUT_DB_PATH`, `SMARTCUT_DADOS_DIR`, `SMARTCUT_RELATORIOS_DIR`, `SMARTCUT_CERT_KEY` | Injetadas pelo Electron no app instalado; em dev use só para apontar para uma cópia do banco. |

O `.env` da raiz não é lido por nenhum processo (servia ao docker-compose,
removido).

---

## Rodar em desenvolvimento

```bash
# Backend — http://localhost:8000/docs
cd backend
py -3.12 -m uvicorn main:app --reload

# Frontend — http://localhost:5173 (proxy de /api para o 8000)
cd frontend
npm run dev

# Ou tudo no Electron (sobe Vite, espera e abre o app; o Electron sobe o uvicorn)
npm run electron-dev
```

Notas:

- No boot o backend **aplica as migrations novas** e, fora do `--reload`, faz
  um backup do banco. Com `--reload` não há backup no boot (cada arquivo
  salvo reiniciaria o backend).
- Em dev a pasta de dados é `backend/` (`backend/smartcut.db`,
  `backend/uploads/`) e os relatórios são lidos de `relatorios/` na raiz.
- O log do boot mostra `Motor v2 disponível (spyrrow …, ortools …)`; sem ele, o
  encaixe não funciona.

---

## Banco de dados e migrations

O schema é governado por Alembic (`backend/alembic/versions/`, versionado no
git). O boot do backend roda `services/db_migracoes.aplicar_migracoes()`.

Fluxo para mudar o schema:

```bash
cd backend
# 0. Backup do banco de dev (o --reload aplica a migration nova sozinho!)
copy smartcut.db smartcut.db.bak-antes-<mudanca>
# 1. Edite o model em models/*.py
# 2. Gere a migration
py -3.12 -m alembic revision --autogenerate -m "descreva_a_mudanca"
# 3. REVISE o arquivo gerado (autogenerate erra; SQLite precisa de batch_alter_table)
# 4. Aplique e confira que não sobrou diferença
py -3.12 -m alembic upgrade head
py -3.12 -m alembic check
```

- **Nunca editar uma migration já aplicada** (em dev ou em alguma
  instalação). Corrija com uma migration nova.
- Banco com tabelas mas sem versão registrada interrompe o boot — o sistema
  nunca "carimba" uma versão sem criar a estrutura.

### Testar com dados reais

Teste de ordem de corte real **só em cópia do banco**:

```bash
cd backend
py -3.12 -m scripts.medir_oc <id-da-oc>             # mede o que está gravado
py -3.12 -m scripts.medir_oc <id-da-oc> --simular   # regera e mede (na cópia em %TEMP%)
```

Para rodar o backend inteiro numa cópia: `set SMARTCUT_DB_PATH=<cópia>.db`
antes do uvicorn.

### Montagem do banco de produção

`backend/scripts/montar_banco_producao.py` gera uma pasta de dados nova (banco
na estrutura atual + arquivos) juntando o financeiro do banco instalado com os
cadastros do banco de dev. Os bancos de entrada são abertos só para leitura.
Uso e o que é copiado estão no cabeçalho do script; o resultado é copiado para
`%APPDATA%\smartcut` com o SmartCut fechado.

---

## Testes e qualidade

```bash
# Backend (de backend/)
py -3.12 -m pytest                      # suíte completa (banco em memória/temporário)
py -3.12 -m pytest --cov                # com cobertura
py -3.12 -m ruff check .                # lint
py -3.12 -m ruff format .               # formatação

# Frontend (de frontend/)
npm run lint
npm test                                # vitest
npm run build

# Electron (raiz) — sincronização dos relatórios
npm run test:electron
```

- Os testes do backend nunca tocam `backend/smartcut.db` nem a pasta de dados
  real: a fixture do `conftest.py` aponta tudo para pastas temporárias.
- `pre-commit` (`.pre-commit-config.yaml`): ruff, eslint, prettier, gitleaks e
  checagens de arquivo. Instale com `py -3.12 -m pre_commit install`.
- **CI** (`.github/workflows/ci.yml`): ruff + pytest, lint + vitest + build do
  frontend, gitleaks e, em tags, o build do instalador sem assinatura.

---

## Build e instalador

| Script (raiz) | O que faz |
|---|---|
| `npm run build-frontend` | `vite build` → `frontend/dist/` |
| `npm run build-backend` | PyInstaller (`backend/smartcut.spec`) → `electron/bin/smartcut-backend.exe` |
| `npm run dist` | build do frontend + backend + instalador (sem assinatura) → `release/` |
| `npm run dist-quick` | só frontend + instalador — **reusa o exe do backend que já está em `electron/bin`** |
| `npm run dist:assinado` | instalador assinado (`electron/release-build.js`); falha se não houver certificado |
| `npm run registrar-relatorios` | registra os hashes dos modelos em `electron/relatorios-hashes.json` (rodado pelos `dist*`) |

- Mudou algo no backend? Rode `npm run build-backend` antes do `dist-quick`.
- Biblioteca nova no backend que o PyInstaller não acha sozinho: acrescentar
  em `hiddenimports` no `smartcut.spec`.
- **Testar o app empacotado sem mexer no `%APPDATA%\smartcut` real**:
  `"release\win-unpacked\SmartCut.exe" --user-data-dir=<pasta temporária>`.
- O instalador leva `relatorios/` como `resources/relatorios-padrao` e só o
  `assets/favicon.ico`.

### Assinatura (opcional)

Crie `release.env` na raiz (no `.gitignore`):

```ini
CSC_LINK=C:\caminho\certificado-de-codigo.pfx
CSC_KEY_PASSWORD=<senha>
```

e rode `npm run dist:assinado`. Também aceita as variáveis de ambiente
`CSC_LINK`/`CSC_KEY_PASSWORD` (ou `WIN_CSC_*`).

---

## Release

1. Atualize a versão em `package.json` (raiz), `frontend/package.json` e
   `backend/main.py` (`version=` do FastAPI).
2. Se mudou modelo de relatório, confira se o `registrar-relatorios` vai
   registrar a versão nova (é automático nos scripts `dist*`).
3. Rode a suíte completa (backend, frontend, electron).
4. `npm run dist` (ou `dist:assinado`).
5. Teste o instalador com `--user-data-dir` temporário e, se possível, sobre
   uma cópia da pasta de dados de produção.
6. Publique `SmartCut Setup <versão>.exe` e o `latest.yml` no endereço de
   `SMARTCUT_UPDATE_URL` (atualização automática) ou entregue o instalador.
7. Guarde o instalador fora do projeto e apague `release/`.

### Atualização automática — teste local

```bash
# release/ com uma versão MAIOR que a instalada
py -3.12 -m http.server 8002 --directory release
set SMARTCUT_UPDATE_URL=http://127.0.0.1:8002
"C:\caminho\do\SmartCut.exe"
```

O `smartcut.log` mostra a versão nova, o download e, ao fechar o app, a
instalação.

---

## Estrutura do repositório

```
SmartCut/
├── backend/            FastAPI
│   ├── main.py         app, registro das rotas, boot (migrations, backup, relatórios)
│   ├── config.py       settings (backend/.env)
│   ├── routers/        rotas HTTP (/api/v1/...)
│   ├── services/       regras de negócio
│   │   ├── nesting_v2/     motor de encaixe (spyrrow + CP-SAT) e decisor do enfesto
│   │   ├── planejamento/   plano de corte por produto, estimador, custo/qualidade
│   │   └── relatorios/     engine Jinja2 e fontes de dados dos relatórios
│   ├── models/         tabelas (SQLAlchemy)
│   ├── schemas/        entrada/saída (Pydantic)
│   ├── parsers/        PLT, DXF, ADS
│   ├── alembic/        migrations (versions/ é versionado)
│   ├── scripts/        backup_sqlite, medir_oc, montar_banco_producao
│   └── tests/          pytest
├── frontend/src/       React: pages/, components/, api/ (uma função por rota), auth/
├── electron/           main.js, backend.js, preload.js, relatorios-sync.js, bin/
├── relatorios/         modelos de relatório (vão no instalador)
├── assets/             ícone do instalador
└── docs/               esta documentação (histórico em docs/historico/)
```
