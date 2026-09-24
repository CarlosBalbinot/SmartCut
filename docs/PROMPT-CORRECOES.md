# PROMPT DE EXECUÇÃO — Correção de problemas do SmartCut

Você é um engenheiro de software sênior trabalhando no projeto **SmartCut** (sistema de gestão têxtil: `D:\Estudos - VSC\SmartCut`). Sua tarefa é resolver, **em partes e sequencialmente**, todos os problemas listados abaixo, sem pular nenhum item. Nenhum dos problemas listados é opcional, salvo indicação contrária.

## Regras gerais de execução (aplicam-se a TODAS as partes)

1. **Não quebre funcionalidade existente.** Antes e depois de cada mudança, o sistema deve continuar rodando: `py -3.12 -m uvicorn main:app --reload` no backend e `npm run dev` no frontend.
2. **Mantenha o estilo do projeto**: PT-BR em mensagens de erro, envelope de resposta `{"data": ..., "error": None}`, comentários explicativos em português, mesmo padrão de imports.
3. **Commits pequenos e atômicos**: um commit por problema (ou por grupo coeso), com mensagem descritiva em português. Nada de commit gigante.
4. **A cada mudança de segurança sensível**, atualize também a documentação inline existente (comentários e `docs/` quando aplicável).
5. **Não remova funcionalidade que esteja em uso**, mesmo que esteja documentada como "legado" — verifique usos antes de apagar (faça a limpeza só daquilo que estiver comprovadamente morto).
6. Antes de começar cada parte, leia os arquivos envolvidos por completo para não basear a mudança em suposições.
7. Ao final de cada parte, rode uma verificação básica de sanidade (imports OK, backend sobe, frontend builda com `npm run build` no `frontend/`).

---

## Parte 1 — Segurança crítica: autenticação e segredos JWT

### 1.1. Segredo JWT do painel do vendedor forjável (CRÍTICO)
- **Problema**: Em `backend/services/auth_service.py`, o segredo do JWT do vendedor é lido com `os.getenv("SECRET_KEY", "change-me-in-production")`. O arquivo `.env` **nunca é carregado para `os.environ`** (o pydantic-settings de `config.py` carrega o `.env` apenas para os campos de `Settings`, não altera variáveis de ambiente do processo). Portanto `_SECRET` fica no valor padrão público `"change-me-in-production"` na prática — qualquer pessoa consegue **forjar um token JWT e se autenticar como qualquer vendedor** nos endpoints protegidos por `get_vendedor_atual` (`backend/dependencies.py`), que confiam apenas no `sub` do token.
- **O que fazer**:
  - Unificar a origem do segredo: criar um único mecanismo de resolução de segredo usado pelos **dois** sistemas JWT (vendedor e admin).
  - Prioridade de resolução do segredo: (a) variável de ambiente real, (b) valor definido em `backend/.env` (carregado explicitamente), (c) em runtime no app Electron, segredo derivado/guardado via `safeStorage` do Electron (ver Parte 6), (d) nunca fallback para string fixa pública em código de produção.
  - Remover **todos os defaults de segredo hardcoded**: `"change-me-in-production"` (auth_service.py), `"smartcut-default-secret-change-in-production"` e `"smartcut-dev-jwt-secret-CHANGE-ME"` (config.py), `"chave-secreta-aqui"` (docker-compose), `"smartcut-secret-key-2024"` (`.env` raiz). Se um default existir, que seja apenas para ambiente de dev detectado explicitamente (ex.: flag) e com warning em log no startup.
- **Critério de aceitação**: com o app rodando em produção (ou modo empacotado), todos os JWT (admin e vendedor) são assinados com segredos criptograficamente fortes e únicos por instalação/ambiente; não existe mais segredo em texto no código; um token não é aceito pelo outro sistema (admin vs vendedor) mesmo que o algoritmo seja o mesmo.

### 1.2. Dois sistemas JWT paralelos com segredos distintos
- **Problema**: O projeto tem dois pares independentes de token: `auth_service.py` (vendedor, usa `SECRET_KEY` via `os.getenv`) e `services/usuario_service.py` (admin, usa `settings.jwt_secret_key`). Código duplicado de `criar_token`/`verificar_token`/`decodificar_token`, e o segredo de cada um evolui independentemente — um pode ficar em default sem ninguém perceber.
- **O que fazer**: unificar em um único módulo de autenticação compartilhado (ex.: dentro de `services/`) que exponha: criação/validação de token, hash/verificação de senha (hoje há `auth_service.hash_senha` com bcrypt puro e `usuario_service.hash_senha` com passlib — duas formas de hashear senha no mesmo projeto; unificar num só lugar). Manter claim `sub` diferenciada (ex.: prefixo `ven:` vs `adm:`) para que um token de um sistema jamais valha no outro.
- **Critério de aceitação**: um único módulo de auth; senha e JWT com uma implementação só; testes manuais: token de admin não autentica endpoints de vendedor e vice-versa.

### 1.3. Sem proteção contra força bruta e sem política de senha
- **Problema**: os endpoints `POST /api/v1/vendedor/login` (backend/routers/auth.py) e `POST /api/v1/auth/login` e `POST /api/v1/auth/setup` não têm rate limit, lockout por tentativas ou validação mínima de senha (`LoginInput`, `LoginAdminInput`, `SetupInput` aceitam qualquer senha, inclusive vazia/curta). Tokens duram 8h e o logout é stateless (o token continua válido até expirar).
- **O que fazer**:
  - Adicionar limitação de tentativas por usuário/IP com atraso progressivo ou bloqueio temporário (pode ser em memória simples, sem depender de infra externa).
  - Validação mínima de senha (ex.: mínimo 8 caracteres) em cadastro (`setup`), troca de senha (`PATCH /me`) e nas credenciais de vendedor (`POST /vendedores/{id}/credenciais`), com mensagem clara em PT-BR.
  - Avaliar e implementar uma forma de revogação/invalidação de sessão (ex.: versão de token ou lista de invalidação) OU documentar explicitamente a limitação.
- **Critério de aceitação**: vários logins falhos em sequência são bloqueados temporariamente; senhas curtas são rejeitadas; mensagens de erro não revelam se o usuário existe.

### 1.4. Token em localStorage no renderer
- **Problema**: `frontend/src/services/api.js` e `frontend/src/auth/AuthContext.jsx` guardam o token admin em `localStorage` (`smartcut_admin_token`), vulnerável a exfiltração caso o renderer tenha qualquer XSS. O painel do vendedor faz o mesmo.
- **O que fazer**: migrar o armazenamento do token para onde não seja acessível a scripts da página: (a) cookie `HttpOnly` + `Secure` via backend, ou (b) armazenamento via `electronAPI` usando `safeStorage` do Electron (item presente no preload `electron/preload.js`). Manter o `apiFetch` injetando o token automaticamente, mas lendo do novo local. Lembre-se: o mesmo frontend roda em navegador (dev via Vite) e no Electron — escolha uma solução que funcione nos dois modos (no navegador, HTTP-Only cookie; no Electron, `safeStorage`).
- **Critério de aceitação**: o token não fica mais legível em `localStorage`; login/logout/rotação continuam funcionando nos dois ambientes.

---

## Parte 2 — Segurança crítica: exposição de arquivos e reforço do Electron

### 2.1. `/uploads` montado publicamente sem autenticação (CRÍTICO)
- **Problema**: `backend/main.py` faz `app.mount("/uploads", StaticFiles(directory=settings.upload_dir))` sem nenhuma checagem de auth. Dentro de `uploads/` ficam **XMLs de NF-e assinados** (`uploads/nfe/Geradas/*.xml`, `Enviadas/`, `SolicCancelamento/`, `CartasDeCorrecaoEnviadas/`), logos da empresa e outros uploads. No Docker (`uvicorn --host 0.0.0.0`) qualquer pessoa na rede baixa documentos fiscais.
- **O que fazer**: remover o `StaticFiles` público e servir arquivos por endpoint autenticado e autorizado (ex.: `GET /api/v1/uploads/...`) que: exija `get_current_user` + permissão do módulo correspondente; **nunca** exponha os XMLs de NF-e a quem não tem permissão fiscal (idealmente só via o próprio módulo NF-e); valide o caminho (bloquear `..`/traversal) e sirva só dentro de `upload_dir`. Alternativa aceitável: continuar servindo via StaticFiles, mas com middleware de auth global cobrindo `/uploads`.
- **Critério de aceitação**: sem token não se baixa nenhum arquivo de `/uploads`; usuário sem permissão fiscal não baixa XML de NF-e; path traversal retorna 403/404.

### 2.2. `webSecurity: false` no Electron (CRÍTICO)
- **Problema**: `electron/main.js` cria a `BrowserWindow` com `webSecurity: false`, desativando a política de mesma origem. Isso existe porque o frontend é carregado via `file://` (ou `localhost:5173`) e precisa chamar `http://127.0.0.1:8000` — o que o CORS atual (só `localhost:5173`) bloquearia.
- **O que fazer** (em conjunto com o item CORS abaixo):
  - Registrar um protocolo customizado (ex.: `app://`) com `protocol.handle` no Electron para servir o `frontend/dist` com origem própria.
  - Voltar `webSecurity: true`.
  - Adicionar **Content-Security-Policy** no `frontend/index.html` (sem `unsafe-inline` desnecessário; alinhar com as necessidades do Vite e do fontes locais).
- **Critério de aceitação**: o app empacotado carrega o frontend via protocolo próprio, `webSecurity` fica `true`, e as chamadas à API funcionam sem abrir exceção de segurança.

### 2.3. `shell.openExternal` sem whitelist de protocolo
- **Problema**: `electron/main.js` repassa **qualquer** URL capturada em `setWindowOpenHandler` para `shell.openExternal(url)`, incluindo esquemas perigosos (`file:`, `smb:`, custom schemes de outros apps).
- **O que fazer**: validar o protocolo antes de abrir (apenas `http:` e `https:`); negar o restante com log.
- **Critério de aceitação**: `shell.openExternal` nunca recebe URL fora de `http(s)`.

### 2.4. CORS restrito a `localhost:5173`
- **Problema**: `backend/main.py` tem `allow_origins=["http://localhost:5173"]`. Com `webSecurity: true` + protocolo `app://` (ou `file://`), a origem não bate e as chamadas seriam bloqueadas.
- **O que fazer**: ajustar a lista de origens permitidas para incluir a origem usada pelo Electron (o protocolo customizado) e, em dev, `http://localhost:5173`. Em produção (Docker), avaliar se o backend precisa ser chamado pelo navegador (mesma origem via proxy) — preferir sempre mesma-origem.
- **Critério de aceitação**: navegador (dev) e Electron (produção) fazem chamadas sem erro de CORS e sem `webSecurity: false`.

### 2.5. Vazamento de erro interno em 500
- **Problema**: `backend/main.py` registra um `@app.exception_handler(Exception)` que devolve `str(exc)` cru no corpo do 500 — vaza detalhes de banco/stack para o cliente (via API e docs).
- **O que fazer**: logar a exceção completa (servidor/logs), responder corpo genérico em PT-BR (ex.: `"Erro interno"`), e garantir que `HTTPException` continue sendo tratada pelo handler padrão (retornar o `detail` só quando for exception explícita da aplicação).
- **Critério de aceitação**: 500 não revela SQL, paths internos nem stack; o erro completo está no log.

---

## Parte 3 — Configuração, segredos e infraestrutura Docker

### 3.1. Segredos hardcoded no docker-compose e `.env`
- **Problema**: `docker-compose.yml` contém `POSTGRES_PASSWORD: senha`, `SECRET_KEY: chave-secreta-aqui`; o `.env` raiz contém `DATABASE_URL=postgresql://postgres:root@localhost:8844/...` e `SECRET_KEY=smartcut-secret-key-2024`; `backend/.env` tem chaves reais. Não existe `.env.example` versionado como referência.
- **O que fazer**:
  - Criar `.env.example` (raiz e backend) com valores placeholder e comentários de qual chave vai em cada ambiente.
  - Substituir valores hardcoded do `docker-compose.yml` por variáveis interpoladas de um `.env` do compose (nunca commitar o `.env` do compose).
  - Garantir `.gitignore` mantendo `.env` fora do versionamento (já cobrem, confirmar).
  - Gerar segredos fortes (ex.: `openssl rand -hex 32`) e documentar o procedimento de geração/rotação.
- **Critério de aceitação**: nenhuma credencial real em arquivo versionado; `docker compose config` não exibe segredo em texto; novo dev consegue subir o stack seguindo o `.env.example`.

### 3.2. Docker: portas expostas desnecessariamente e modo reload em container
- **Problema**: `docker-compose.yml` publica `5432:5432` (Postgres) e `8000:8000` (backend) para a rede; o comando do backend usa `--reload`; o `Dockerfile` do backend expõe `--host 0.0.0.0`; o frontend em container roda Vite dev (sem build/nginx).
- **O que fazer**:
  - Publicar no host apenas o que for necessário (frontend e, para debug, backend); expor Postgres só à rede interna do compose (remover `ports` ou limitar a `127.0.0.1`).
  - Remover `--reload` do comando de produção do compose (ou separar um `docker-compose.dev.yml` de um `docker-compose.prod.yml`).
  - Criar Dockerfile de produção para o frontend (build estático + nginx, com proxy reverso `/api` → backend) — ou deixar claro que o compose atual é **somente dev** e colocar isso no README.
- **Critério de aceitação**: `docker compose up` não expõe o banco na rede; não roda `--reload` em produção; existe caminho de build de produção do frontend.

### 3.3. Sem estratégia de backup de banco
- **Problema**: nenhum backup em nenhum modo: SQLite no desktop (arquivo em `userData`) e Postgres no Docker.
- **O que fazer**:
  - Descrever e implementar backup simples: para SQLite, cópia segura periódica (com `WAL` checkpoint) do `smartcut.db` para pasta de backup com retenção de N dias; para Postgres, job/serviço opcional no compose com `pg_dump` em volume separado.
  - Documentar o procedimento de restore.
- **Critério de aceitação**: script/mecanismo de backup documentado e testável; restore validado num ambiente de teste.

---

## Parte 4 — Certificado digital NF-e (sensibilidade máxima)

### 4.1. `.pfx` armazenado junto do projeto
- **Problema**: o certificado digital real (`Certificados/*.pfx`) fica na raiz do repositório (só gitignorado), junto do código-fonte. Sujeito a vazamento em backup/sincronização, e o `nfe_service.py` referencia pasta `../Certificados` relativa ao cwd do processo — **quebrada** no app empacotado (cwd = `userData`, então `../Certificados` não existe).
- **O que fazer**: mover o `.pfx` para fora da árvore de código; o caminho deve vir de configuração (variável de ambiente/settings) e, no desktop, apontar para local escolhido pelo usuário (com diálogo de seleção). Remover qualquer dependência de caminho relativo à raiz do projeto. Garantir que o `.gitignore` nunca permita `.pfx`/`.p12` versionados (já cobre, confirmar e reforçar com um teste de `git check-ignore`).

### 4.2. Senha do certificado em base64 reversível no banco
- **Problema**: `backend/services/venda_service.py` grava `certificado_senha` como `base64.b64encode(senha)` — qualquer leitor do banco (ou atacante com acesso ao arquivo SQLite) recupera a senha do certificado.
- **O que fazer**:
  - No desktop: guardar a senha criptografada com o cofre do sistema (Windows DPAPI via `safeStorage` do Electron no processo main, passando para o backend por IPC) — o banco guarda apenas um blob cifrado ou um identificador.
  - No Docker/navegador: exigir a senha em runtime (não persistir) ou cifrar com chave mestre fornecida por ambiente; documentar os trade-offs.
  - Nunca devolver a senha em qualquer endpoint de leitura (confirmar que `empresa_fiscal_out` mascara; manter mascarada).
- **Critério de aceitação**: a senha do certificado não é recuperável em texto claro a partir do banco; fluxo de teste do certificado (`POST /configuracao-empresa/fiscal/testar-certificado`) continua funcionando.

---

## Parte 5 — Permissões e regime de banco de dados

### 5.1. Bug de permissão no módulo NF-e
- **Problema**: `backend/routers/nfe.py` usa `require_permission("fiscal_transmitir", "ver")`, `require_permission("fiscal_cancelar", "ver")` e `require_permission("fiscal_carta_correcao", "ver")` para **operações de escrita** (transmitir, cancelar, carta de correção) — usuário com apenas leitura fiscal pode transmitir/cancelar notas.
- **O que fazer**: definir ações de execução no `ACOES_VALIDAS` de `backend/models/usuario.py` (ex.: `fiscal_transmitir` → ação `executar`/`transmitir`; `fiscal_cancelar` → `cancelar`; `fiscal_carta_correcao` → `criar`), corrigir as dependências do `nfe.py` e, se necessário, migrar/seed das permissões existentes nos bancos em uso (SQLite dev e Postgres), lembrando que admins (`is_admin`) já passam sempre.
- **Critério de aceitação**: usuário não-admin com só `ver` no módulo fiscal não consegue chamar transmitir/cancelar/CC-e (403); admin continua podendo.

### 5.2. Migrações Alembic não versionadas (CRÍTICO para evolução)
- **Problema**: `.gitignore` exclui `backend/alembic/versions/*.py` (só mantém `.gitkeep`). O schema real vem de `Base.metadata.create_all` no startup (`backend/main.py` lifespan) — que **cria** tabelas mas **não altera** tabelas existentes. Time não consegue reproduzir o banco, mudanças de schema ficam invisíveis/impossíveis de aplicar em instalações existentes.
- **O que fazer**:
  - Versionar as migrações: remover o trecho do `.gitignore`, commitar as migrações existentes como ponto de partida (baseline das tabelas atuais).
  - A partir daí, todo change de schema via nova migração Alembic; `create_all` deve deixar de ser a fonte de verdade (no mínimo, só criar em dev/primeiro boot se não houver tabelas).
  - Documentar o fluxo: `alembic upgrade head` no boot do backend (desktop e Docker) com revisão já alinhada ao schema.
- **Critério de aceitação**: clonando o repo num ambiente limpo, `alembic upgrade head` reproduz o schema completo; uma alteração de tabela de teste gera migração versionada; `create_all` não mascara mais drift.

### 5.3. SQLite no desktop vs Postgres no Docker (divergência)
- **Problema**: o desktop usa SQLite (via `SMARTCUT_DB_PATH`), o Docker usa Postgres 15; o código mantém comportamento para os dois sem estratégia única; `database.py` usa `check_same_thread: False` (específico SQLite) incondicionalmente.
- **O que fazer**:
  - Definir Postgres como fonte de verdade (recomendado) OU SQLite em todos os lugares; em qualquer caso, eliminar comportamento duplicado/divergente.
  - Se manter SQLite no desktop: documentar como evoluir schema com migrações (item 5.2), e tratar `check_same_thread`/pool de forma condicionada ao driver.
  - Rodar a suíte de testes (quando existir, ver Parte 8) nos dois bancos.
- **Critério de aceitação**: não existe mais código com caminhos incompatíveis entre os dois bancos; migrações funcionam em ambos; documentado qual é o banco de cada deploy.

---

## Parte 6 — Desktop: entrega, assinatura e atualização

### 6.1. Instalador Windows sem assinatura digital
- **Problema**: o build usa `CSC_IDENTITY_AUTO_DISCOVERY=false` (assinatura desabilitada) — instalações reais vão esbarrar em SmartScreen/antivírus.
- **O que fazer**: configurar assinatura opcional via certificado de código (var. de ambiente `CSC_LINK`/`CSC_KEY_PASSWORD`) sem quebrar o build local sem certificado; documentar o processo no `docs/ELECTRON.md` (ou equivalente).
- **Critério de aceitação**: build com certificado disponível produz `.exe`/instalador assinado; build sem certificado continua funcionando (desenvolvimento).

### 6.2. Sem auto-update
- **Problema**: existe `release/latest.yml` (gerado pelo electron-builder) mas nenhum código de atualização — o app não se atualiza sozinho.
- **O que fazer**: implementar atualização com `electron-updater` (canal com `latest.yml` já emitido), com verificação em `app.whenReady`, baixando e instalando no fechamento, e notificação ao usuário em PT-BR; considerar assinatura obrigatória antes de habilitar (macOS exige, Windows recomenda).
- **Critério de aceitação**: uma versão "falsa" mais nova num repo local de publish é detectada e atualizada num teste manual.

### 6.3. Segredo de produção do desktop derivado de `safeStorage`
- **Problema**: (relacionado à Parte 1) o app empacotado precisa de um segredo JWT estável por instalação.
- **O que fazer**: gerar segredo na primeira execução, cifrar com `safeStorage` (Electron main) e persistir em `userData`; o backend deve receber esse segredo via ambiente (como já recebe `SMARTCUT_DB_PATH`/`UPLOAD_DIR` em `electron/backend.js`).
- **Critério de aceitação**: duas instalações do app não compartilham segredo; reabrir o app mantém o mesmo segredo; o segredo não aparece em log nem em texto claro em disco.

---

## Parte 7 — Limpeza de dead code e consolidação do frontend

### 7.1. Camada de API duplicada no frontend
- **Problema**: coexistem `frontend/src/services/api.js` (arquivo monolítico com ~40 grupos de métodos) e `frontend/src/api/*.js` (17 módulos por domínio). Os comentários do próprio `api.js` indicam migração em andamento (ex.: `pedidosVendaApi foi removido… unificado em src/api/pedidos.js`), com convenções misturadas (uns usam `fetch` puro, outros `apiFetch` autenticado).
- **O que fazer**: eleger **um** padrão (recomendado: módulos em `src/api/` por domínio) e migrar todo consumo; remover do `services/api.js` tudo que tiver equivalente; manter no `services/api.js` apenas utilities compartilhadas (`apiFetch`, `mensagemErro`). Garantir que **toda** chamada autenticada passe por `apiFetch` (injeta token).
- **Critério de aceitação**: nenhuma página importa métodos duplicados de duas origens; busca por um endpoint revela definição em um único lugar.

### 7.2. Routers e endpoints mortos no backend
- **Problema**: `backend/routers/pedidos.py` existe mas **nunca é incluído** no `main.py`; `frontend/src/services/api.js` documenta endpoints quebrados que nunca foram portados: `duplicar`, `resumo-corte`, `relatorio-pdf`, `metricas`, etc. em `/pedidos-venda/...`.
- **O que fazer**:
  - Decidir por cada endpoint: implementar no router vivo (`pedidos_venda.py`) ou remover definitivamente.
  - Remover do `api.js` (ou `src/api/pedidos.js`) tudo que ficar decidido como não existente, sem deixar comentário "endpoint não existe" em produção.
  - Remover `routers/pedidos.py` se confirmado que nada o importa (validar com busca em todo o repo).
- **Critério de aceitação**: todo método exposto no frontend tem endpoint real funcionando (ou foi removido); busca por "não existe em pedidos_venda" retorna vazio.

### 7.3. Dupla hierarquia de tecidos (legado × nova)
- **Problema**: convivem `routers/tecidos.py` + `models/tecido.py` (legado) e a nova hierarquia `modelos_tecido/cores_tecido/lotes_tecido`. O `main.py` monta ambos.
- **O que fazer**: mapear quais telas/APIs ainda consomem o legado; se só a nova hierarquia é usada, remover o legado (router, model, schemas, chamadas frontend) após confirmar; caso contrário, documentar explicitamente a fase de transição. **Não remover sem validação de uso.**
- **Critério de aceitação**: há uma única fonte de verdade para "tecido" no código ou uma rota de migração documentada.

---

## Parte 8 — Testes, qualidade e dependências

### 8.1. Zero testes automatizados
- **Problema**: não existe nenhum teste (backend `backend/tests/` ou frontend). O módulo NF-e — o mais crítico — está cheio de notas "não pôde ser validado contra homologação real" (`backend/services/nfe_service.py`), e sem testes o risco de regressão é altíssimo.
- **O que fazer**:
  - Backend: pytest + httpx/TestClient com banco SQLite temporário por teste. Cobertura mínima obrigatória:
    1. Auth/RBAC: login admin e vendedor, token válido/expirado/inválido, `require_permission` concedendo/negando, o caso do item 5.1 (não-transmitir sem permissão).
    2. Pedidos/Precificação: cálculo de totais, reaplicação de tabela de preço.
    3. Clientes/Moldes: CRUD e importação de arquivos (DXF/PLT/ADS) com arquivo de fixture pequeno.
    4. NF-e: montagem do XML (estrutura e valores), dígito verificador da chave (inclusive a função `_mod11_dv`), assinatura com certificado de teste (pode gerar um self-signed em tempo de teste), fluxo de transmitir com mock do zeep/requests.
  - Frontend: testes do `mensagemErro`/`apiFetch` (Vitest) e ao menos um teste de componente crítico (login) com React Testing Library.
  - Configurar: `backend/pytest.ini`/`pyproject.toml` e script `test` no `frontend/package.json`.
- **Critério de aceitação**: `pytest` e `npm test` rodam limpos; cobertura mínima de ~60% nos módulos acima; CI (Parte 9) executa esses testes.

### 8.2. Dependências defasadas
- **Problema**: `backend/requirements.txt` pinado em versões antigas (fastapi 0.111.0, uvicorn 0.29.0, pydantic 2.7.1, sqlalchemy 2.0.30, alembic 1.13.1 — todas de 2024, com CVEs conhecidas em versões posteriores). Frontend sem auditoria (`npm audit`) incorporada.
- **O que fazer**:
  - Backend: atualizar para as versões estáveis atuais compatíveis com Python 3.12 (fastapi, uvicorn, pydantic/pydantic-settings, sqlalchemy, alembic, starlette), executar a suíte de testes e validar o build PyInstaller (o `smartcut.spec` precisa continuar empacotando). Manter o pin de `bcrypt==4.0.1` (documentado) ou migrar passlib→bcrypt direto se conveniente.
  - Frontend: rodar `npm audit` e resolver (ou documentar) vulnerabilidades; atualizar vite/react conforme compatibilidade.
  - Adicionar checagem de dependências ao fluxo de dev (CI).
- **Critério de aceitação**: `pip-audit`/`npm audit --audit-level=high` sem achados críticos/altos não resolvidos; app roda e empacota após atualização.

### 8.3. Sem lint/formatação/pre-commit
- **Problema**: nenhum ESLint, Ruff/Black, ou pre-commit.
- **O que fazer**: configurar ESLint + Prettier (frontend) e Ruff (backend, com formato semelhante ao padrão já usado), adicionar `pre-commit` com hooks (lint, format check, trailing whitespace, secrets scan — ex.: `gitleaks`/`detect-secrets` para pegar futuros vazamentos de segredo), e scripts `lint`/`format` nos package.json + `pyproject.toml`.
- **Critério de aceitação**: `npm run lint`, `ruff check .` e `pre-commit run --all-files` passam sem erros novos (definir regras com tolerância para o código legado existente).

---

## Parte 9 — CI/CD e automação

### 9.1. Sem pipeline de CI
- **Problema**: não existe `.github/` (nem outro CI). Tudo é manual.
- **O que fazer**: criar workflow (GitHub Actions, ou documentar alternativa) com os jobs:
  1. **Backend**: setup Python 3.12, instalar deps, `ruff check`, `pytest`.
  2. **Frontend**: `npm ci`, `npm run lint`, `npm test`, `npm run build`.
  3. **Build desktop** (opcional, em tag): `npm run dist` (sem assinatura) e upload de artefato.
  4. **Segredos**: job `gitleaks` (ou `detect-secrets`, cujo resultado deve ser **zero segredos**).
- **Critério de aceitação**: push/PR roda os 3 primeiros jobs; scan de segredos falha se algum segredo for commitado.

### 9.2. Logs e observabilidade
- **Problema**: logs via `fs.appendFileSync` no Electron e stdout no backend; sem rotação, níveis estruturados ou correlação.
- **O que fazer**:
  - Backend: usar `logging` com formato estruturado (timestamp, nível, módulo, request_id), iniciar em `main.py`; logar exceções internas completas mas nunca dado sensível (senha, certificado, token).
  - Electron: manter arquivo em `userData`, adicionar rotação simples (tamanho máximo → rotacionar N arquivos) e garantir que o `open-pdf-blob`/IPC não loguem conteúdo de arquivos sensíveis.
- **Critério de aceitação**: erro de produção rastreável com request_id; logs não contêm segredos.

---

## Parte 10 — Organização do repositório e documentação

### 10.1. Artefatos de build commitados
- **Problema**: `backend/services/nesting/engine/Release/` contém binários compilados (`addon.node`, `.o`, `.d`) **rastreados no git** (aparecem em `git ls-files`).
- **O que fazer**: remover do tracking (`git rm --cached`), adicionar ao `.gitignore` os diretórios `Release/`/`build/` do engine de nesting, e documentar como o artefato é gerado no setup (binário deve ser produzido no build e empacotado pelo `smartcut.spec` via datas).
- **Critério de aceitação**: `git ls-files | grep Release` vazio; build do backend ainda gera o executável com o addon.

### 10.2. `docs/` inteiro fora do versionamento
- **Problema**: `.gitignore` ignora `docs/` — ROADMAP, ESTRUTURA, FUNCIONALIDADES, FINANCEIRO, ELECTRON etc. não são versionados (somem em outro checkout).
- **O que fazer**: manter `docs/` no git (ajustar `.gitignore` mantendo apenas o que for interno — ver se há distinção necessária entre documentação pública e interna), e versionar os arquivos atuais de documentação.
- **Critério de aceitação**: `git ls-files docs/` lista os documentos; nova máquina tem a documentação.

### 10.3. Organização do `main.py` e da inicialização
- **Problema**: `backend/main.py` tem uma sequência longa e manual de `include_router` (30+), misturando legado e novo, com comentários de seção.
- **O que fazer**: reorganizar o registro dos routers de forma declarativa (lista estruturada por domínio) mantendo a ordem de rota atual (para não mudar precedência de caminhos), e documentar qual agrupamento é legado.
- **Critério de aceitação**: `main.py` mais curto e legível; rotas registradas idênticas às atuais (comparar `/docs` ou rota a rota).

### 10.4. Endpoints e secrets no `.env` raiz vs `backend/.env`
- **Problema**: existem dois `.env` (raiz e `backend/`) com valores diferentes para a mesma finalidade (`DATABASE_URL`, `SECRET_KEY`), o que causa confusão sobre qual vale (o `Settings` do pydantic carrega `backend/.env`; o `auth_service` lê env do processo).
- **O que fazer**: **unificar a fonte de configuração** — um único mecanismo (settings do pydantic para tudo), carregando sempre o mesmo `.env`; eliminar leitura via `os.getenv` espalhada; documentar no `.env.example` quais variáveis existem e onde cada uma é usada. (Conecta-se ao item 1.1.)
- **Critério de aceitação**: alterando `SECRET_KEY`/`DATABASE_URL` em um único lugar, todo o sistema (auth admin, auth vendedor, banco) reflete a mudança.

---

## Critérios de aceitação gerais (finais)

Ao concluir todas as partes, verifique:
1. `pytest` e `npm test` passam; `ruff check`, `npm run lint` e `pre-commit run --all-files` passam.
2. Scan de segredos (gitleaks/detect-secrets) retorna **zero** no repositório.
3. `npm run dist` gera o instalador; `alembic upgrade head` reproduz o schema do zero.
4. Nenhum segredo, caminho absoluto de máquina ou binário de build está no git.
5. O app funciona: login admin (setup), login vendedor, CRUD de pedido, geração de NF-e (homologação) e painel financeiro — sem `webSecurity: false`.
6. Ao final, entregue um resumo por parte: o que mudou, e o que ficou pendente/aberto com justificativa.