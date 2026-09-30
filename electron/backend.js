const { spawn, execSync } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');
const os = require('os');
const crypto = require('crypto');
const { app, safeStorage } = require('electron');

// item 9.2: mesmo logger do main.js (rotação em userData/smartcut.log). O
// build-backend (PyInstaller) é rotulado com [backend.js] para contexto.
const logger = require('./logger.js');
const { sincronizarRelatorios } = require('./relatorios-sync.js');

let backendProcess = null;

function log(msg) {
  logger.info(`[backend.js] ${msg}`);
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

// ── Chave de cifragem dos segredos em repouso (item 4.2) ─────────────────────
// A senha do certificado nunca fica em texto claro no banco do backend: o
// backend cifra (AES-256-GCM) com uma chave que recebe por ambiente. Aqui a
// chave é gerada UMA vez por instalação, gravada protegida pelo cofre do
// sistema (safeStorage — DPAPI no Windows) em userData/smartcut-cert-key.bin
// e repassada ao backend somente via SMARTCUT_CERT_KEY. O renderer e os
// scripts da página nunca têm acesso a este arquivo. Sem keyring disponível,
// usa o prefixo "plain:" como fallback (mesma política do token, item 1.4).
function certificadoKeyPath() {
  return path.join(app.getPath('userData'), 'smartcut-cert-key.bin');
}

function garantirChaveCertificado() {
  const caminho = certificadoKeyPath();
  if (fs.existsSync(caminho)) {
    const dados = fs.readFileSync(caminho);
    if (safeStorage.isEncryptionAvailable()) return safeStorage.decryptString(dados);
    const texto = dados.toString('utf8');
    return texto.startsWith('plain:') ? texto.slice(6) : null;
  }
  const chave = crypto.randomBytes(32).toString('base64url');
  const dados = safeStorage.isEncryptionAvailable()
    ? safeStorage.encryptString(chave)
    : Buffer.from(`plain:${chave}`, 'utf8');
  fs.writeFileSync(caminho, dados);
  return chave;
}

// ── Segredo JWT estável por instalação (item 6.3) ──────────────────────────
// Sem um SECRET_KEY fixo, o painel do vendedor geraria tokens novos a cada
// boot do backend — sessões cairiam reiniciando o app e o segredo caberia a
// um valor efêmero (item 1.1). Aqui o segredo é gerado UMA vez por instalação,
// cifrado com o cofre do sistema (safeStorage/DPAPI) em
// userData/smartcut-jwt-secret.bin e repassado ao backend via SECRET_KEY —
// mesmo padrão do item 4.2. Cada instalação tem segredo próprio (randomBytes
// por máquina/usuário), ele nunca aparece em log e em texto claro só quando o
// keyring está indisponível (fallback "plain:", mesma política do token).
function jwtSegredoPath() {
  return path.join(app.getPath('userData'), 'smartcut-jwt-secret.bin');
}

function garantirSegredoJwt() {
  const caminho = jwtSegredoPath();
  if (fs.existsSync(caminho)) {
    const dados = fs.readFileSync(caminho);
    if (safeStorage.isEncryptionAvailable()) return safeStorage.decryptString(dados);
    const texto = dados.toString('utf8');
    return texto.startsWith('plain:') ? texto.slice(6) : null;
  }
  // 48 bytes > 32 (mínimo recomendado para HS256): base64url sem padding.
  const segredo = crypto.randomBytes(48).toString('base64url');
  const dados = safeStorage.isEncryptionAvailable()
    ? safeStorage.encryptString(segredo)
    : Buffer.from(`plain:${segredo}`, 'utf8');
  fs.writeFileSync(caminho, dados);
  return segredo;
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
    const certificadosDir = path.join(userData, 'Certificados');
    // Modelos de relatório editáveis pelo usuário em userData/relatorios,
    // atualizados a partir de resources/relatorios-padrao sem sobrescrever
    // edições (electron/relatorios-sync.js). Em desenvolvimento o backend
    // continua lendo a pasta relatorios/ da raiz do projeto.
    const relatoriosDir = path.join(userData, 'relatorios');

    log(`userData: ${userData}`);
    log(`dbPath: ${dbPath}`);
    log(`uploadDir: ${uploadDir}`);
    log(`certificadosDir: ${certificadosDir}`);
    try {
      fs.mkdirSync(certificadosDir, { recursive: true });
    } catch (e) {
      log(`erro ao criar pasta de certificados: ${e.message}`);
    }
    log(`relatoriosDir: ${relatoriosDir}`);
    try {
      sincronizarRelatorios(
        path.join(process.resourcesPath, 'relatorios-padrao'),
        relatoriosDir,
        path.join(__dirname, 'relatorios-hashes.json'),
        log,
      );
    } catch (e) {
      log(`erro ao sincronizar modelos de relatório: ${e.message}`);
    }
    log(`spawning exe...`);

    // Item 4.2: a chave de cifragem das senhas em repouso é gerada uma vez por
    // instalação e vai para o backend somente via ambiente (o renderer nunca a
    // vê). A chave fica protegida pelo cofre do sistema (safeStorage/DPAPI)
    // em userData/smartcut-cert-key.bin.
    let certKey = '';
    try {
      certKey = garantirChaveCertificado();
      log(`chave de certificado pronta (${certKey ? 'ok' : 'indisponível'})`);
    } catch (e) {
      log(`erro ao obter chave de certificado: ${e.message}`);
    }

    // Item 6.3: segredo JWT estável por instalação (SECRET_KEY) — evita que o
    // backend recaia no segredo efêmero (item 1.1) e derrube as sessões a cada
    // boot. Mesmo mecanismo do item 4.2: gera uma vez, cifra com safeStorage e
    // injeta somente via ambiente.
    let jwtSecret = '';
    try {
      jwtSecret = garantirSegredoJwt();
      log(`segredo JWT pronto (${jwtSecret ? 'ok' : 'indisponível'})`);
    } catch (e) {
      log(`erro ao obter segredo JWT: ${e.message}`);
    }

    backendProcess = spawn(exePath, [], {
      cwd: userData,
      env: {
        ...process.env,
        SMARTCUT_DB_PATH: dbPath,
        UPLOAD_DIR: uploadDir,
        CERTIFICADO_DIR: certificadosDir,
        SMARTCUT_RELATORIOS_DIR: relatoriosDir,
        SMARTCUT_CERT_KEY: certKey,
        SECRET_KEY: jwtSecret,
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
