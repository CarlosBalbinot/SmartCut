// logger.js — Log do processo principal do Electron com rotação simples (Parte 9.2).
//
// Mantém o arquivo em userData/smartcut.log; ao atingir o tamanho máximo, o
// arquivo atual é rotacionado (smartcut.log → smartcut.log.1, ...) mantendo N
// backups. Ambos os módulos do processo principal (main.js e backend.js) usam
// este módulo, então todo o histórico do app passa pela mesma rotação.
//
// NUNCA logar conteúdo de arquivos sensíveis (PDFs, certificados .pfx/.p12,
// tokens, base64 de documentos) — apenas caminhos e mensagens de erro.

'use strict';

const fs = require('fs');
const path = require('path');

// 512 KB por arquivo; mantém smartcut.log + smartcut.log.1 .. .3 (≈2 MB total).
const MAX_LOG_BYTES = 512 * 1024;
const MAX_ROTATED = 3;

let logFile = null;
let bytesEscritos = 0;

function escrever(nivel, msg) {
  const line = `[${new Date().toISOString()}] [${nivel}] ${msg}\n`;
  process.stdout.write(line);
  if (!logFile) return;
  try {
    fs.appendFileSync(logFile, line);
    bytesEscritos += Buffer.byteLength(line, 'utf8');
    if (bytesEscritos >= MAX_LOG_BYTES) rotacionar();
  } catch (_) {
    // O log nunca pode derrubar o app: em caso de erro de escrita, segue só no stdout.
  }
}

function rotacionar() {
  if (!logFile) return;
  const maisAntigo = `${logFile}.${MAX_ROTATED}`;
  try { fs.unlinkSync(maisAntigo); } catch (_) {}
  for (let i = MAX_ROTATED - 1; i >= 1; i -= 1) {
    const de = `${logFile}.${i}`;
    const para = `${logFile}.${i + 1}`;
    try {
      if (fs.existsSync(de)) fs.renameSync(de, para);
    } catch (_) {}
  }
  try {
    if (fs.existsSync(logFile)) fs.renameSync(logFile, `${logFile}.1`);
  } catch (_) {}
  bytesEscritos = 0;
}

function init(userDataDir) {
  try {
    fs.mkdirSync(userDataDir, { recursive: true });
    logFile = path.join(userDataDir, 'smartcut.log');
    // Arquivo legado já estourado (ex.: sequência interrompida): rotaciona no boot.
    if (fs.existsSync(logFile) && fs.statSync(logFile).size >= MAX_LOG_BYTES) rotacionar();
    bytesEscritos = fs.existsSync(logFile) ? fs.statSync(logFile).size : 0;
  } catch (_) {
    logFile = null;
  }
}

module.exports = {
  init,
  info: (msg) => escrever('INFO', msg),
  warn: (msg) => escrever('WARN', msg),
  error: (msg) => escrever('ERROR', msg),
};