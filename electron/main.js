const { app, BrowserWindow, shell, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawnBackend, killBackend } = require('./backend.js');

const isDev = process.env.NODE_ENV === 'development';

let mainWindow = null;
let logPath = null;
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
  const line = `[${new Date().toISOString()}] ${msg}\n`;
  process.stdout.write(line);
  if (logPath) {
    try { fs.appendFileSync(logPath, line); } catch (_) {}
  }
}

function initLog() {
  try {
    logPath = path.join(app.getPath('userData'), 'smartcut.log');
    fs.writeFileSync(logPath, '');
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
      webSecurity: false,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
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

app.whenReady().then(async () => {
  initLog();
  ensureComprasFolder();
  log(`pasta Compras: ${comprasPath}`);
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
      const frontendPath = findFrontend();
      log(`loadFile: ${frontendPath}`);
      win.loadFile(frontendPath);
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
