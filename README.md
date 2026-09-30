# SmartCut

Sistema inteligente de gestão e otimização de corte têxtil — backend
**FastAPI** (`backend/`), frontend **React + Vite** (`frontend/`) e aplicativo
desktop **Electron** (`electron/`).

---

## Índice

- [1. Variáveis de ambiente e segredos](#1-variáveis-de-ambiente-e-segredos)
- [2. Desenvolvimento (desktop)](#2-desenvolvimento-desktop)
- [3. Docker](#3-docker)
- [4. Backup e restore](#4-backup-e-restore)
- [5. Certificado digital (NF-e)](#5-certificado-digital-nfe)

---

## 1. Variáveis de ambiente e segredos

**Nunca** commite `.env` nem segredos reais. Os arquivos `.env*` já estão no
`.gitignore`. O que é versionado são os templates `.env.example` (raiz e
`backend/`).

### Criando seu `.env`

```bash
cp .env.example .env          # na raiz (compose/Docker)
cp backend/.env.example backend/.env   # backend local (fora do Docker)
```

Ajuste os valores. Itens obrigatórios com valor real:

| Variável | Onde é usada | Papel |
|---|---|---|
| `SECRET_KEY` | backend (JWT) | Assina tokens do painel do vendedor e administrativo. **Crítica.** |
| `POSTGRES_PASSWORD` | compose (Docker) | Senha do banco nos serviços `postgres`/`backend`/`backup`. |
| `DATABASE_URL` | backend local | `backend/.env`: `sqlite:///./smartcut.db` (desktop). |

Sobre o **certificado digital NF-e** (itens 4.1/4.2):

| Variável | Quando definir |
|---|---|
| `CERTIFICADO_DIR` | Pasta padrão do `.pfx`, **fora da árvore de código** (ex.: `userData/Certificados`). No desktop o Electron injeta sozinho. |
| `CERT_SENHA_KEY` | Fora do desktop (dev/Docker): chave mestre que cifra a senha do certificado em repouso. **No desktop não defina** — o app gera e protege a própria chave com o cofre do sistema (ver seção 5). |

### Gerando segredos fortes

```bash
py -3.12 -c "import secrets; print(secrets.token_hex(32))"
# ou, com OpenSSL:
openssl rand -hex 32
```

Use o valor gerado como `SECRET_KEY`. Para `POSTGRES_PASSWORD` use algo forte
(ex.: `py -3.12 -c "import secrets; print(secrets.token_urlsafe(24))"`).

### Rotação de segredos

Para `SECRET_KEY`:

1. Gere um novo valor e troque no `.env` (e no `backend/.env`, se usar local);
2. Reinicie os serviços (`docker compose -f docker-compose.prod.yml restart backend`)
   ou o desktop — **os JWTs antigos deixam de validar** e os usuários refazem o
   login;
3. Mantenha o valor antigo por segurança enquanto confirma que tudo voltou.

Para `POSTGRES_PASSWORD`:

1. Troque no `.env`;
2. `docker exec -it smartcut_postgres_prod psql -U smartcut -c "ALTER USER smartcut PASSWORD 'novo';"`;
3. Reinicie `backend` e `backup` (`docker compose -f docker-compose.prod.yml restart backend backup`).

---

## 2. Desenvolvimento (desktop)

Pré-requisitos: Python 3.12 e Node 20+.

```bash
# Backend
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py -3.12 -m uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev        # http://localhost:5173

# Desktop (opcional, consome os dois acima)
cd electron
npm install
npm start          # ou o fluxo de build do desktop
```

O Vite redireciona `/api` para o backend em `localhost:8000` (o antigo
`/uploads` público foi removido — arquivos saem por `GET /api/v1/uploads/...`
autenticado). **CSP**: o `index.html` carrega a política estrita de produção;
em dev o próprio Vite troca a meta por uma versão compatível com o HMR.

---

## 3. Docker

### Desenvolvimento (`docker-compose.yml`)

```bash
cp .env.example .env   # gerencie SECRET_KEY e POSTGRES_PASSWORD
docker compose up -d
```

- Postgres **só em `127.0.0.1:5432`** (não exposto à rede);
- Backend em `127.0.0.1:8000` com `--reload` e código montado;
- Frontend (Vite dev/HMR) em `http://localhost:5173`.

### Produção (`docker-compose.prod.yml`)

```bash
docker compose -f docker-compose.prod.yml up -d
```

- Postgres **sem porta no host** (rede interna do compose);
- Backend sem `--reload` e sem volume de código (build imutável);
- Frontend = build de produção servido pelo nginx em
  `http://<servidor>:${FRONTEND_PORT:-8080}` (proxy `/api` → backend);
- Serviço `backup` faz `pg_dump` diário (ver seção 4).

> O compose de produção recusa iniciar sem `POSTGRES_PASSWORD` e `SECRET_KEY`
> no `.env` (interpolação `:?`) — nenhum segredo fraco por padrão.

### Exposição de portas (item 3.2)

| Serviço | Dev | Prod |
|---|---|---|
| Postgres | `127.0.0.1:5432` | não exposto |
| Backend | `127.0.0.1:8000` | não exposto (opcional no prod, ver comentário no arquivo) |
| Frontend | `127.0.0.1:5173` | `0.0.0.0:8080` (ponto de entrada) |

---

## 4. Backup e restore

### SQLite — desktop

O backend faz backup automático **no startup e a cada `BACKUP_INTERVAL_SEC`**
(6 h por padrão) para a pasta `backups/` ao lado do `smartcut.db` (no desktop:
`<userData>/backups`), mantendo `BACKUP_RETENTION_DIAS` (7) dias. Cada backup é
uma cópia consistente com **checkpoint passivo do WAL** incluindo os arquivos
`-wal`/`-shm`.

Configuração (em `.env` ou variáveis de ambiente):

```bash
BACKUP_DIR=                # vazio = "backups" ao lado do .db
BACKUP_RETENTION_DIAS=7    # dias de retenção
BACKUP_INTERVAL_SEC=21600  # intervalo entre backups (6h)
```

**Backup manual** (agendador do Windows/Linux, por exemplo):

```bash
py -3.12 scripts/backup_sqlite.py --db C:\caminho\smartcut.db --backup-dir C:\caminho\backups --retention-dias 7
```

**Restore (SQLite):**

1. Feche o aplicativo (desktop) ou pare o backend;
2. Copie o backup mais recente por cima do `smartcut.db`
   (`xcopy`/`cp` do `backups/smartcut_<timestamp>` para o local do `.db`);
3. **Remova** `smartcut.db-wal` e `smartcut.db-shm` se existirem (o SQLite
   reconstrói a partir do arquivo principal);
4. Abra o aplicativo e confira os dados.

### Postgres — Docker

O serviço `backup` do `docker-compose.prod.yml` roda o `pg_dump` **diariamente**
compactado (`gzip`) no volume `postgres_backups`, retendo
`BACKUP_RETENTION_DIAS` dias.

**Restore (Postgres):**

```bash
# dentro do container backup
zcat /backups/smartcut_<timestamp>.sql.gz | PGPASSWORD=... psql -h postgres -U smartcut -d smartcut_db
```

**Validação regular:** execute um restore num ambiente de teste e confira
contagens de tabelas principais (`empresa`, `pedido_venda`, `notas_fiscais`).

---

## 5. Certificado digital (NF-e)

### Onde fica o `.pfx` (4.1)

O certificado fica numa pasta de certificados e o caminho gravado na
configuração da empresa é **absoluto** — nenhuma referência relativa à raiz do
projeto (o antigo `../Certificados` relativo ao `cwd` quebrava no app
empacotado, onde `cwd` = `userData`). Pasta convencional, nesta ordem:

1. `CERTIFICADO_DIR` definido (no desktop o Electron injeta
   `<userData>/Certificados`, fora da árvore de código);
2. senão, a pasta `Certificados/` na raiz do repositório (convenção do
   projeto — cada usuário coloca o próprio `.pfx` lá manualmente; o app roda
   local).

Na tela de Configurações Fiscais o usuário escolhe o arquivo pelo **diálogo
nativo** (desktop) ou digita o caminho. `.gitignore`, `.dockerignore` e
`git check-ignore` garantem que `.pfx`/`.p12`/`.cer` jamais entrem no
versionamento ou nas imagens.

### Senha cifrada em repouso (4.2)

O banco guarda apenas um **blob cifrado** (`enc:v1:...`, AES-256-GCM); a senha
em texto claro ou em base64 reversível não existe mais no SQLite. A chave nunca
fica no banco. Fontes da chave:

- **Desktop**: o Electron gera uma chave por instalação, guarda no cofre do
  sistema (`safeStorage`/DPAPI em `userData/smartcut-cert-key.bin`) e injeta a
  chave só na variável de ambiente `SMARTCUT_CERT_KEY` do backend.
- **Docker/servidor**: o operador define `CERT_SENHA_KEY` no ambiente
  (secret manager, `.env` do compose). Sem a chave, o backend **recusa salvar**
  uma senha nova com mensagem clara.
- **Senhas gravadas antes da correção** (base64 legado) continuam usáveis em
  leitura e são **migradas automaticamente** para o formato cifrado no startup
  assim que houver chave.

**Trade-offs documentados**

- Quem lê **apenas o banco** não recupera a senha em nenhum cenário (sem chave,
  `enc:v1:` é inutilizável).
- Quem tiver **banco + chave** (mesmo usuário/instalação) consegue decifrar —
  no desktop isso exige acesso ao cofre do sistema do usuário; em Docker, à
  chave mestre do operador.
- Navegador sem `CERT_SENHA_KEY`: a alternativa é **não persistir** e exigir a
  senha a cada uso (runtime) — hoje o fluxo persistido exige a chave mestre.
- Trocar a chave (`CERT_SENHA_KEY`) **invalida** as senhas gravadas (blob não
  decifra): os usuários devem informar a senha novamente na tela fiscal.

## 6. Banco de dados e migrações (Parte 5)

### Regime por ambiente (5.3)

Cada modo de operação usa um banco; o backend não tem código específico por
banco — só as migrações e o driver mudam:

| Ambiente | Banco | Como o backend resolve a URL |
|---|---|---|
| Desktop (Electron empacotado) | SQLite | `SMARTCUT_DB_PATH` (diretório `userData`) |
| Desenvolvimento local (`uvicorn main:app`) | SQLite | `DATABASE_URL` no `backend/.env` |
| Docker dev e prod (`docker-compose*.yml`) | Postgres 15 | `DATABASE_URL` injetada pelo compose |

A resolução é única (`database.resolver_url`) e o driver específico só é
configurado para SQLite (`check_same_thread`) — nada de argumentos SQLite
vazando para o Postgres.

### Migrações Alembic versionadas (5.2)

O schema **não é mais criado por `Base.metadata.create_all` no boot** (ele só
criava tabelas novas e nunca alterava tabelas existentes). Agora:

- `backend/alembic/versions/` contém a **baseline completa** do schema atual
  (gerada por autogenerate, cross-dialeto SQLite/Postgres) e, a partir daí,
  uma migração por mudança — tudo **commitado no git**.
- O boot aplica as migrações em todos os ambientes:
  - **Desktop**: `services/db_migracoes.aplicar_migracoes()` no startup do
    FastAPI (bancos antigos criados por `create_all` são registrados na
    baseline com `stamp head`, sem reexecutar DDL; depois segue `upgrade head`).
  - **Docker**: `alembic upgrade head && uvicorn ...` (Dockerfile e compose).
- `alembic check` confere se os models batem com o banco migrado (zero drift).

**Fluxo para evoluir o schema** (pode repetir em cada mudança):

```bash
cd backend
# 1. Edite o model (models/*.py).
# 2. Gere a migração a partir da diferença entre models e banco:
py -3.12 -m alembic revision --autogenerate -m "descreva_a_mudanca"
# 3. REVISE o arquivo gerado em alembic/versions/ (nunca confie cegamente).
# 4. Aplique localmente:
py -3.12 -m alembic upgrade head
# 5. Confira que não sobrou drift:
py -3.12 -m alembic check
```

Nos contêineres e no desktop a migração é aplicada automaticamente no boot.

> Migrações antigas (nunca commitadas e quebradas no SQLite) foram arquivadas
> em `backend/alembic/legado/` (fora do git e da imagem) e substituídas pela
> baseline.

### Permissões fiscais (5.1)

Operações de escrita do módulo NF-e exigem agora **ações próprias de
execução** — `ver` não autoriza mais transmitir/cancelar/CC-e:

| Módulo | Ação exigida |
|---|---|
| `fiscal_transmitir` | `executar` |
| `fiscal_cancelar` | `cancelar` |
| `fiscal_carta_correcao` | `criar` |

Usuários não-admin que já tinham `ver` nesses módulos ganham a ação de
execução automaticamente (sincronização idempotente no boot), preservando a
capacidade anterior; admins (`is_admin`) continuam passando sempre.
