# ELECTRON.md — App Desktop (Empacotamento, Assinatura e Atualização)

> Documento de referência do app desktop do SmartCut (Electron + backend PyInstaller).
> Cobre o que antes eram "passos de implementação", agora já implementados, e em
> especial os itens 6.1 (assinatura opcional), 6.2 (atualização automática) e
> 6.3 (segredo JWT por instalação) de `PROMPT-CORRECOES.md`.

## Por que Electron?

O SmartCut precisa de acesso ao sistema de arquivos para:
- Ler arquivos PLT/DXF/ADS diretamente de qualquer pasta
- Salvar PDFs localmente sem limitações do browser
- Rodar o backend FastAPI embutido sem precisar de terminal
- Funcionar como aplicativo instalado, com atalho no desktop

O Electron foi escolhido por:
- Stack conhecida (React permanece igual)
- Experiência prévia com Turbo Cookies (mesmo padrão)
- Comunidade grande, bem documentada
- Auto-updater nativo (electron-updater)
- Geração de instalador .exe para Windows

---

## Arquitetura atual (implementada)

```
Electron (processo principal)
    │
    ├── main.js
    │     • Registra o esquema app:// (item 2.2/2.4) ANTES do ready
    │     • Cria a BrowserWindow (webSecurity: true, contextIsolation: true)
    │     • Mostra loading.html enquanto o backend sobe
    │     • Configura o auto-update (item 6.2) no whenReady
    │     • IPC seguro para token/sessão (itens 1.4, 4.1) e PDFs
    │
    ├── backend.js
    │     • spawnBackend(): PyInstaller (produção) ou uvicorn (dev)
    │     • Health check em localhost:8000/health
    │     • Gera/abre chave de certificado (item 4.2) e segredo JWT
    │       por instalação (item 6.3), ambos cifrados com safeStorage
    │     • killBackend(): taskkill /T /F no Windows
    │
    ├── preload.js
    │     • contextBridge: getVersion, apiUrl, getToken/setToken/clearToken,
    │       selecionarCertificado, openPdfBlob, Compras
    │
    └── Frontend
          • Dev:      localhost:5173 (Vite, proxy /api → 8000)
          • Produção: app://bundle/index.html servido pelo protocolo próprio
```

Em produção (instalador .exe):
- Python + dependências empacotados com PyInstaller (`npm run build-backend`)
- React buildado como arquivos estáticos (`npm run build-frontend`)
- Electron serve os estáticos via `app://bundle` com CSP estrita (não usa `file://`)
- Banco SQLite em `%APPDATA%/SmartCut/smartcut.db` (embutido no desktop);
  o servidor usa PostgreSQL (ver `docker-compose.yml`)

---

## Instalador, assinatura e atualização (itens 6.1 e 6.2)

### 6.1 — Assinatura OPCIONAL do instalador

A assinatura de código (Authenticode) é **opcional por design**: o build local
sem certificado continua funcionando normalmente (o caminho padrão do
electron-builder desativa a descoberta automática de certificados).

Scripts (`package.json`):

| Script | Uso | Comportamento |
|---|---|---|
| `npm run dist` | Build local / teste | `CSC_IDENTITY_AUTO_DISCOVERY=false` → **não assina** |
| `npm run dist-quick` | Build rápido local | Idem, sem PyInstaller |
| `npm run dist:assinado` | Release real | `electron/release-build.js`, `forceCodeSigning` → **falha rápido** sem certificado |

Para gerar um instalador **assinado**:

1. Tenha um certificado de código Windows (.pfx) e crie `release.env` na raiz
   (arquivo **gitignored**):
   ```ini
   # release.env — NÃO VERSIONAR (credenciais sensíveis)
   CSC_LINK=<caminho-absoluto-do-certificado.pfx>
   CSC_KEY_PASSWORD=<senha-do-certificado>
   ```
   Equivalentes aceitos via variável de ambiente/CI: `CSC_LINK`,
   `CSC_KEY_PASSWORD` (e `WIN_CSC_LINK`/`WIN_CSC_KEY_PASSWORD`).
2. `npm run dist:assinado`
   - Sem `CSC_LINK` → o script aborta **antes** de gerar um instalador não
     assinado (release não pode sair "achado por acaso").
   - Com o certificado → instalador e executáveis assinados (SHA-256
     timestamp incluído), reduzindo avisos do SmartScreen.

> Nota: versões instaladas não assinadas ainda recebem atualização automática
> se o repositório estiver configurado — mas para distribuir para terceiros,
> assine o instalador (o Windows recomenda; no macOS seria obrigatório para
> auto-update, e o desktop é Windows-only).

### 6.2 — Atualização automática (electron-updater)

Implementada com `electron-updater` (dep **de produção**, vai no pacote),
canal `generic` consumindo o `latest.yml` que o electron-builder emite na pasta
`release/` junto com o instalador NSIS.

- **Ativa somente em app empacotado** e quando a variável de ambiente
  `SMARTCUT_UPDATE_URL` aponta para o repositório (ex.:
  `https://downloads.vaidosafitness.com/smartcut/`). Sem ela, o app loga
  "auto-update desativado" e segue normal.
- Verificação no `app.whenReady`; download em segundo plano;
  `autoInstallOnAppQuit` instala no fechamento; diálogo em PT-BR oferece
  "Reiniciar agora" quando o download termina.
- Eventos registrados em log (`smartcut.log` no userData): verificação, nova
  versão, progresso (a cada 25%), download concluído e erros.

**Teste manual com repositório local ("versão falsa mais nova")**:

1. Gere dois builds com versões crescentes no `package.json`
   (ex.: `1.0.1` instalada e `1.0.2` no `release/`).
2. Sirva a pasta do build mais novo:
   ```
   py -m http.server 8002 --directory release
   ```
3. Rode o app instalado com a variável apontando para o repositório local:
   ```
   set SMARTCUT_UPDATE_URL=http://127.0.0.1:8002
   SmartCut.exe
   ```
4. O log deve mostrar a nova versão detectada, o download, e ao fechar o app
   a instalação é aplicada (o app reabre na versão nova).

---

## Segredo JWT por instalação (item 6.3)

O backend precisa de um `SECRET_KEY` estável para emitir/validar JWT. Sem ele
(item 1.1), o backend cairia num segredo efêmero e **todas as sessões seriam
invalidadas a cada boot** (típico em desktop: reiniciou o app, deslogou todo
mundo).

Solução implementada em `electron/backend.js` (mesmo padrão do item 4.2):

1. Na primeira execução do app empacotado, gera `randomBytes(48)` (base64url,
   robusto para HS256) — **uma vez por instalação**.
2. Cifra com `safeStorage` (cofre do SO — DPAPI no Windows) e grava em
   `userData/smartcut-jwt-secret.bin`.
3. Injeta no backend **somente via ambiente** ao spawnar o executável
   PyInstaller: `SECRET_KEY=<segredo>`.
4. Fallback documentado: sem keyring, grava com prefixo `plain:` (mesma
   política do token da sessão, item 1.4) — o renderer/scripts da página nunca
   têm acesso ao arquivo.

Resultado: duas instalações **não compartilham** segredo; reabrir o app
mantém o mesmo segredo (sessões persistem); o segredo nunca aparece em log nem
em texto claro no disco.

---

## Estrutura de arquivos (atual)

```
SmartCut/
├── electron/
│   ├── main.js          # Janela, app://, CSP, auto-update (6.2), IPC
│   ├── backend.js       # spawn/kill backend, chaves cifradas (4.2/6.3)
│   ├── preload.js       # contextBridge seguro
│   ├── release-build.js # build ASSINADO (6.1) — não vai no pacote
│   └── loading.html     # tela de loading enquanto o backend sobe
├── frontend/            # React (Vite), build → frontend/dist
├── backend/             # FastAPI; PyInstaller → electron/bin/smartcut-backend.exe
├── docs/ELECTRON.md     # este documento
├── release/             # saída do electron-builder (gitignored)
└── package.json         # build config do electron-builder + scripts
```

Configuração do electron-builder fica no campo `build` do `package.json`
(NSIS, pt_BR, ícone `assets/favicon.ico`, permitir escolher pasta de
instalação). Não existe `electron-builder.yml`.

---

## Scripts no package.json (atual)

```json
{
  "scripts": {
    "electron-dev": "concurrently \"npm run dev --prefix frontend\" \"wait-on http://localhost:5173 && cross-env NODE_ENV=development electron .\"",
    "build-frontend": "npm run build --prefix frontend",
    "build-backend": "cd backend && py -3.12 -m PyInstaller smartcut.spec --clean --distpath ../electron/bin",
    "predist": "npm run build-frontend && npm run build-backend",
    "dist": "cross-env CSC_IDENTITY_AUTO_DISCOVERY=false electron-builder --win",
    "dist-quick": "npm run build-frontend && cross-env CSC_IDENTITY_AUTO_DISCOVERY=false electron-builder --win",
    "dist:assinado": "node electron/release-build.js"
  },
  "dependencies": {
    "electron-updater": "^6.3.9"
  }
}
```

---

## Variáveis de ambiente usadas pelo Electron

| Variável | Onde | Efeito |
|---|---|---|
| `NODE_ENV=development` | `electron-dev` | Modo dev (Vite, sem app://, sem auto-update) |
| `SMARTCUT_DB_PATH` | injetada no spawn | Caminho do SQLite no userData |
| `UPLOAD_DIR` | injetada no spawn | Pasta de uploads no userData |
| `CERTIFICADO_DIR` | injetada no spawn | Pasta de certificados digitais no userData |
| `SMARTCUT_CERT_KEY` | injetada no spawn | Chave AES-256-GCM das senhas em repouso (item 4.2) |
| `SECRET_KEY` | injetada no spawn | Segredo JWT estável por instalação (item 6.3) |
| `SMARTCUT_UPDATE_URL` | lida pelo main | URL do repositório de atualizações (item 6.2) |
| `CSC_LINK` / `CSC_KEY_PASSWORD` | build (`dist:assinado`) | Certificado de código Windows (item 6.1) |
