const { spawn, execSync } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');
const os = require('os');
const { app } = require('electron');

let backendProcess = null;

function log(msg) {
  const line = `[${new Date().toISOString()}] [backend.js] ${msg}\n`;
  process.stdout.write(line);
  try {
    const logPath = path.join(app.getPath('userData'), 'smartcut.log');
    fs.appendFileSync(logPath, line);
  } catch (_) {}
}

function findPython() {
  const probeCmds = ['py -3.12', 'python3.12', 'python3', 'python'];
  for (const cmd of probeCmds) {
    try {
      const exe = execSync(
        `${cmd} -c "import sys; print(sys.executable)"`,
        { env: { ...process.env }, shell: true, timeout: 5000 }
      ).toString().trim();
      if (exe && fs.existsSync(exe)) {
        log(`Python encontrado via "${cmd}": ${exe}`);
        return exe;
      }
    } catch (_) {}
  }

  const knownPaths = [
    'C:\\Python311\\python.exe',
    'C:\\Python312\\python.exe',
    path.join(os.homedir(), 'AppData', 'Local', 'Programs', 'Python', 'Python311', 'python.exe'),
    path.join(os.homedir(), 'AppData', 'Local', 'Programs', 'Python', 'Python312', 'python.exe'),
    path.join(os.homedir(), 'AppData', 'Local', 'Programs', 'Python', 'Python310', 'python.exe'),
  ];
  for (const p of knownPaths) {
    if (fs.existsSync(p)) {
      log(`Python encontrado em caminho fixo: ${p}`);
      return p;
    }
  }

  throw new Error(
    'Python não encontrado no sistema.\n' +
    'Instale Python 3.12 (python.org) e reinicie o app.'
  );
}

function checkHealth() {
  return new Promise((resolve, reject) => {
    const req = http.get('http://localhost:8000/health', (res) => {
      if (res.statusCode === 200) resolve();
      else reject(new Error(`status ${res.statusCode}`));
      res.resume();
    });
    req.setTimeout(500, () => { req.destroy(); reject(new Error('timeout')); });
    req.on('error', reject);
  });
}

function waitForBackend(maxAttempts = 60, interval = 1000) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    function attempt() {
      checkHealth()
        .then(resolve)
        .catch(() => {
          attempts++;
          if (attempts >= maxAttempts) {
            reject(new Error(`Backend não respondeu após ${maxAttempts}s`));
          } else {
            setTimeout(attempt, interval);
          }
        });
    }
    attempt();
  });
}

function attachLogs(proc) {
  proc.stdout && proc.stdout.on('data', (d) => {
    d.toString().split('\n').filter(Boolean).forEach(l => log(`[stdout] ${l}`));
  });
  proc.stderr && proc.stderr.on('data', (d) => {
    d.toString().split('\n').filter(Boolean).forEach(l => log(`[stderr] ${l}`));
  });
  proc.on('error', (err) => {
    log(`ERRO ao spawnar: ${err.message}`);
    log(`Stack: ${err.stack}`);
  });
  proc.on('exit', (code, signal) => log(`encerrou (exit) — código=${code} sinal=${signal}`));
  proc.on('close', (code, signal) => log(`processo encerrou (close) — code: ${code} signal: ${signal}`));
}

async function spawnBackend() {
  log(`--- spawnBackend iniciado ---`);
  log(`isPackaged: ${app.isPackaged}`);
  log(`resourcesPath: ${process.resourcesPath}`);
  log(`__dirname: ${__dirname}`);

  // Se já estiver rodando (ex: debug com backend separado), reutilizar
  try {
    await checkHealth();
    log('backend já está rodando na porta 8000 — reutilizando');
    return;
  } catch (_) {}

  if (app.isPackaged) {
    // ── Produção: executável PyInstaller ─────────────────────────────────
    const exePath = path.join(process.resourcesPath, 'bin', 'smartcut-backend.exe');
    const exeExists = fs.existsSync(exePath);
    log(`exePath: ${exePath}`);
    log(`exePath exists: ${exeExists}`);

    if (!exeExists) {
      // Listar o que tem em resources/bin para diagnóstico
      const binDir = path.join(process.resourcesPath, 'bin');
      try {
        const binContents = fs.readdirSync(binDir);
        log(`resources/bin contents: ${JSON.stringify(binContents)}`);
      } catch (e) {
        log(`resources/bin inacessível: ${e.message}`);
      }
      throw new Error(`Backend não encontrado em:\n${exePath}`);
    }

    const userData  = app.getPath('userData');
    const dbPath    = path.join(userData, 'smartcut.db');
    const uploadDir = path.join(userData, 'uploads');

    log(`userData: ${userData}`);
    log(`dbPath: ${dbPath}`);
    log(`uploadDir: ${uploadDir}`);
    log(`spawning exe...`);

    backendProcess = spawn(exePath, [], {
      cwd: userData,
      env: {
        ...process.env,
        SMARTCUT_DB_PATH: dbPath,
        UPLOAD_DIR: uploadDir,
      },
      shell: false,
      windowsHide: true,
    });

    log(`spawn retornou — PID: ${backendProcess.pid}`);

  } else {
    // ── Desenvolvimento: Python + uvicorn ─────────────────────────────────
    const pythonExe   = findPython();
    const backendPath = path.join(__dirname, '..', 'backend');
    log(`backendPath: ${backendPath}`);
    log(`pythonExe: ${pythonExe}`);
    log(`spawning uvicorn...`);

    backendProcess = spawn(
      pythonExe,
      ['-m', 'uvicorn', 'main:app', '--reload', '--port', '8000'],
      { cwd: backendPath, env: { ...process.env }, windowsHide: true }
    );
  }

  attachLogs(backendProcess);
  log('aguardando health check...');
  await waitForBackend();
  log('backend pronto!');
}

function killBackend() {
  if (!backendProcess) return;
  const pid = backendProcess.pid;
  backendProcess = null;
  log(`encerrando processo (PID ${pid})...`);
  if (process.platform === 'win32') {
    // execSync bloqueia até o taskkill terminar de fato — spawn assíncrono
    // aqui deixava o smartcut-backend.exe órfão, pois o Electron encerrava
    // antes do taskkill concluir.
    try {
      execSync(`taskkill /PID ${pid} /T /F`, { windowsHide: true });
      log(`processo ${pid} encerrado via taskkill`);
    } catch (e) {
      log(`taskkill falhou (PID ${pid}): ${e.message}`);
    }
  } else {
    try { process.kill(pid, 'SIGTERM'); } catch (e) { log(`SIGTERM falhou: ${e.message}`); }
  }
}

module.exports = { spawnBackend, killBackend };
