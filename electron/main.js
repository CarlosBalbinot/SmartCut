const { app, BrowserWindow, shell, ipcMain, dialog, safeStorage, protocol, net } = require('electron');
const path = require('path');
const fs = require('fs');
const { pathToFileURL } = require('url');
const { spawnBackend, killBackend } = require('./backend.js');
// item 9.2: log do processo principal com rotação simples em userData/smartcut.log.
const logger = require('./logger.js');
// item 6.2: atualização automática (canal latest.yml do electron-builder).
const { autoUpdater } = require('electron-updater');

const isDev = process.env.NODE_ENV === 'development';

// Item 2.2/2.4: protocolo próprio app:// serve o frontend de produção com
// origem estável (app://bundle) — permite webSecurity: true sem depender de
// file://. Deve ser registrado ANTES do evento ready do Electron.
const APP_SCHEME = 'app';
const APP_HOST = 'bundle';

protocol.registerSchemesAsPrivileged([
  {
    scheme: APP_SCHEME,
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
      stream: true,
    },
  },
]);

// Content-Security-Policy aplicada no app empacotado (item 2.2) — espelha a
// meta tag estrita do frontend/index.html. Sem unsafe-inline para scripts:
// o bundle de produção não usa script inline.
const CSP_PRODUCAO = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: http://127.0.0.1:8000",
  "connect-src 'self' http://127.0.0.1:8000",
  "font-src 'self' data:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join('; ');

let mainWindow = null;
let comprasPath = null;

function ensureComprasFolder() {
  comprasPath = path.join(app.getPath('userData'), 'Compras');
  try {
    fs.mkdirSync(comprasPath, { recursive: true });
  } catch (e) {
    log(`erro ao criar pasta Compras: ${e.message}`);
  }
  return comprasPath;
}

function log(msg) {
  logger.info(msg);
}

function initLog() {
  try {
    // item 9.2: arquivo em userData/smartcut.log com rotação (tamanho máx. →
    // N backups). Mantém o histórico entre reinícios; não trunca no boot.
    logger.init(app.getPath('userData'));
    log(`isPackaged: ${app.isPackaged}`);
    log(`resourcesPath: ${process.resourcesPath}`);
    log(`__dirname: ${__dirname}`);
    log(`appPath: ${app.getAppPath()}`);
  } catch (e) {
    console.error('log init error:', e.message);
  }
}

function findFrontend() {
  const candidates = [
    path.join(app.getAppPath(), 'frontend', 'dist', 'index.html'),
    path.join(process.resourcesPath, 'app', 'frontend', 'dist', 'index.html'),
    path.join(process.resourcesPath, 'frontend', 'dist', 'index.html'),
    path.join(__dirname, '..', 'frontend', 'dist', 'index.html'),
  ];
  for (const p of candidates) {
    const exists = fs.existsSync(p);
    log(`  check: ${p} → ${exists ? 'OK' : 'not found'}`);
    if (exists) return p;
  }
  log('  WARNING: nenhum caminho encontrado, usando primeiro como fallback');
  return candidates[0];
}

function createWindow() {
  const iconPath = app.isPackaged
    ? path.join(process.resourcesPath, 'assets', 'favicon.ico')
    : path.join(__dirname, '..', 'assets', 'favicon.ico');
  log(`iconPath: ${iconPath} → ${fs.existsSync(iconPath) ? 'OK' : 'NOT FOUND'}`);

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 600,
    show: false,
    backgroundColor: '#F5F5F7',
    icon: iconPath,
    title: 'SmartCut',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      // Item 2.2: política de mesma origem ATIVA. O frontend de produção é
      // servido pelo protocolo app:// (não file://), então não há motivo
      // para desativar a segurança do Chromium.
      webSecurity: true,
    },
  });

  // Item 2.3: só abrir externamente URLs http(s); qualquer outro esquema
  // (file:, smb:, custom schemes) é negado e registrado no log.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    let protocolo = '';
    try {
      protocolo = new URL(url).protocol;
    } catch (e) {
      log(`setWindowOpenHandler: URL inválida ignorada: ${url} (${e.message})`);
      return { action: 'deny' };
    }
    if (protocolo === 'http:' || protocolo === 'https:') {
      shell.openExternal(url);
    } else {
      log(`setWindowOpenHandler: bloqueei shell.openExternal fora de http(s): ${url}`);
    }
    return { action: 'deny' };
  });

  return mainWindow;
}

ipcMain.handle('get-version', () => app.getVersion());
ipcMain.handle('get-compras-path', () => comprasPath || ensureComprasFolder());
ipcMain.handle('open-compras-folder', () => shell.openPath(comprasPath || ensureComprasFolder()));

// Electron não sabe abrir URLs blob: (usadas para PDFs gerados no renderer,
// ex.: DANFE Simplificada) — não existe arquivo real por trás delas fora do
// contexto do renderer. Por isso o PDF chega aqui em base64, é salvo num
// arquivo temporário e aberto com o aplicativo padrão do sistema.
//
// item 9.2: o conteúdo do PDF (base64Data) NUNCA é logado — só o caminho do
// arquivo temporário e, em caso de falha, a mensagem de erro do shell.
ipcMain.handle('open-pdf-blob', async (event, base64Data, filename) => {
  const tempDir = path.join(app.getPath('temp'), 'smartcut');
  fs.mkdirSync(tempDir, { recursive: true });
  const safeName = (filename || 'documento.pdf').replace(/[\\/:*?"<>|]/g, '_');
  const filePath = path.join(tempDir, `${Date.now()}-${safeName}`);
  fs.writeFileSync(filePath, Buffer.from(base64Data, 'base64'));
  const erro = await shell.openPath(filePath);
  if (erro) log(`erro ao abrir PDF temporário (${filePath}): ${erro}`);
  return filePath;
});

// Item 4.1: o usuário escolhe o certificado digital com o diálogo nativo —
// o .pfx fica em local fora da árvore de código (ex.: userData/Certificados)
// e o caminho é gravado apenas na configuração da empresa. Nada de caminho
// relativo à raiz do projeto. item 9.2: o caminho escolhido não é logado.
ipcMain.handle('selecionar-certificado', async () => {
  try {
    const win = BrowserWindow.getFocusedWindow() || BrowserWindow.getAllWindows()[0];
    const resultado = await dialog.showOpenDialog(win, {
      title: 'Selecionar certificado digital (.pfx / .p12)',
      properties: ['openFile'],
      filters: [{ name: 'Certificados digitais', extensions: ['pfx', 'p12'] }],
    });
    if (resultado.canceled || !resultado.filePaths.length) return null;
    return resultado.filePaths[0];
  } catch (e) {
    log(`erro ao selecionar certificado: ${e.message}`);
    return null;
  }
});

// ── Token de sessão criptografado (item 1.4) ───────────────────────────────
// O token NÃO fica em localStorage: no Electron é gravado criptografado via
// safeStorage (chave do sistema operacional — DPAPI no Windows) num arquivo do
// userData, e o renderer só o obtém/limpa via IPC. Em plataformas sem
// keyring disponível (safeStorage indisponível), grava com prefixo "plain:"
// como fallback documentado (ainda assim o renderer/scripts da página não
// têm acesso direto ao arquivo).
function tokenPath(escopo) {
  const s = String(escopo || 'admin').replace(/[^a-z]/gi, '');
  return path.join(app.getPath('userData'), `smartcut.token.${s}`);
}

ipcMain.handle('token-set', (_e, token, escopo) => {
  try {
    const dados = safeStorage.isEncryptionAvailable()
      ? safeStorage.encryptString(String(token))
      : Buffer.from(`plain:${token}`, 'utf8');
    fs.writeFileSync(tokenPath(escopo), dados);
  } catch (e) {
    log(`erro ao salvar token: ${e.message}`);
  }
});

ipcMain.handle('token-get', (_e, escopo) => {
  try {
    const caminho = tokenPath(escopo);
    if (!fs.existsSync(caminho)) return null;
    const dados = fs.readFileSync(caminho);
    if (safeStorage.isEncryptionAvailable()) return safeStorage.decryptString(dados);
    const texto = dados.toString('utf8');
    return texto.startsWith('plain:') ? texto.slice(6) : null;
  } catch (e) {
    log(`erro ao ler token: ${e.message}`);
    return null;
  }
});

ipcMain.handle('token-clear', (_e, escopo) => {
  try {
    const caminho = tokenPath(escopo);
    if (fs.existsSync(caminho)) fs.unlinkSync(caminho);
  } catch (e) {
    log(`erro ao limpar token: ${e.message}`);
  }
});

// ── Atualização automática (item 6.2) ──────────────────────────────────────
// Usa electron-updater com canal generic (latest.yml gerado pelo
// electron-builder no target NSIS). Só ativa no app EMPACOTADO e quando a
// variável de ambiente SMARTCUT_UPDATE_URL aponta para o repositório de
// distribuição (ex.: https://downloads.vaidosafitness.com/smartcut/).
//
// Para teste local: `python -m http.server 8002 --directory release` (ou
// similar) e rodar o app com SMARTCUT_UPDATE_URL=http://127.0.0.1:8002 — uma
// versão "mais nova" no release/ é detectada, baixada e instalada no fechamento.
function configureAutoUpdate() {
  const urlAtualizacao = process.env.SMARTCUT_UPDATE_URL;
  if (!app.isPackaged) {
    log('auto-update desativado: ambiente de desenvolvimento');
    return;
  }
  if (!urlAtualizacao) {
    log('auto-update desativado: SMARTCUT_UPDATE_URL não definida');
    return;
  }
  log(`auto-update ativo — repositório: ${urlAtualizacao}`);

  autoUpdater.setFeedURL({ provider: 'generic', url: urlAtualizacao });
  autoUpdater.autoDownload = true; // baixa a nova versão em segundo plano
  autoUpdater.autoInstallOnAppQuit = true; // instala no fechamento (NSIS)

  autoUpdater.on('checking-for-update', () => log('auto-update: verificando atualizações...'));
  autoUpdater.on('update-available', (info) => {
    log(`auto-update: nova versão ${info.version} disponível — baixando...`);
  });
  autoUpdater.on('update-not-available', (info) => {
    log(`auto-update: nenhuma atualização (versão atual ${info.version}).`);
  });
  autoUpdater.on('download-progress', (p) => {
    if (p.percent && p.percent % 25 === 0) {
      log(`auto-update: download ${Math.round(p.percent)}%`);
    }
  });
  autoUpdater.on('update-downloaded', async (info) => {
    log(`auto-update: v${info.version} baixada — instalando no fechamento.`);
    const win = BrowserWindow.getAllWindows()[0];
    if (!win || win.isDestroyed()) return;
    // Aviso em português: oferece reiniciar agora (a instalação silenciosa
    // ocorre ao fechar se o usuário escolher "Instalar ao sair").
    const { response } = await dialog.showMessageBox(win, {
      type: 'info',
      title: 'Atualização disponível',
      message: `A versão ${info.version} do SmartCut foi baixada.`,
      detail: 'A atualização será aplicada agora ou ao fechar o aplicativo.',
      buttons: ['Reiniciar agora', 'Instalar ao sair'],
      defaultId: 0,
      cancelId: 1,
    });
    if (response === 0) {
      log('auto-update: reiniciando para instalar');
      autoUpdater.quitAndInstall(false, true); // silencioso + reabre o app
    }
  });
  autoUpdater.on('error', (err) => {
    log(`auto-update: erro — ${err.message}`);
  });

  // Verifica no whenReady, baixa e instala no fechamento (autoInstallOnAppQuit).
  // checkForUpdatesAndNotify() mostra também a notificação nativa ao baixar.
  autoUpdater.checkForUpdatesAndNotify().catch((err) => {
    log(`auto-update: falha na verificação — ${err.message}`);
  });
}

app.whenReady().then(async () => {
  initLog();
  ensureComprasFolder();
  log(`pasta Compras: ${comprasPath}`);

  // item 6.2: verificação de atualização no whenReady (somente app empacotado
  // com SMARTCUT_UPDATE_URL definida). Download em segundo plano; instalação
  // no fechamento ou reinício imediato escolhido pelo usuário.
  configureAutoUpdate();

  // Item 2.2: serve o frontend de produção via app://bundle (substitui o
  // carregamento por file:// com webSecurity:false). Requisições internas
  // (assets, CSS, imagens) são resolvidas pela própria origem app://.
  const frontendDir = path.dirname(findFrontend());
  protocol.handle(APP_SCHEME, async (request) => {
    const url = new URL(request.url);
    const raiz = path.resolve(frontendDir);
    let arquivo = path.resolve(raiz, '.' + decodeURIComponent(url.pathname));

    // Contenção: nunca servir arquivo fora da pasta do frontend.
    if (arquivo !== raiz && !arquivo.startsWith(raiz + path.sep)) {
      arquivo = path.join(raiz, 'index.html');
    }
    if (!fs.existsSync(arquivo) || fs.statSync(arquivo).isDirectory()) {
      arquivo = path.join(raiz, 'index.html'); // fallback SPA
    }

    const resposta = await net.fetch(pathToFileURL(arquivo).toString());
    if (path.basename(arquivo).toLowerCase() === 'index.html') {
      const headers = new Headers(resposta.headers);
      headers.set('Content-Security-Policy', CSP_PRODUCAO);
      return new Response(resposta.body, { status: resposta.status, headers });
    }
    return resposta;
  });

  const win = createWindow();

  // ── Passo 1: mostrar loading enquanto o backend sobe ───────────────────
  const loadingPath = path.join(__dirname, 'loading.html');
  log(`loading screen: ${loadingPath}`);
  win.loadFile(loadingPath);
  win.show();

  try {
    // ── Passo 2: aguardar backend (PyInstaller leva ~10-15s na 1ª execução)
    await spawnBackend();
    log('backend pronto — carregando frontend');

    // ── Passo 3: trocar loading pelo frontend real ─────────────────────────
    if (isDev) {
      win.loadURL('http://localhost:5173');
      win.webContents.openDevTools();
    } else {
      log(`loadURL: app://${APP_HOST}/index.html`);
      win.loadURL(`app://${APP_HOST}/index.html`);
    }

  } catch (err) {
    log(`backend error: ${err.message}`);
    dialog.showErrorBox(
      'Erro ao iniciar o backend',
      `O servidor não pôde ser iniciado:\n\n${err.message}`
    );
    app.quit();
  }
});

app.on('before-quit', () => killBackend());

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
