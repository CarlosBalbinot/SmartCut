// ── Modelos de relatório na pasta de dados do usuário ───────────────────────
// O pacote leva os modelos originais em resources/relatorios-padrao/ (cópia
// da pasta relatorios/ do projeto). O backend instalado lê os modelos de
// userData/relatorios (SMARTCUT_RELATORIOS_DIR), onde o usuário pode editá-los
// pelo Explorer. A cada inicialização, sincronizarRelatorios() leva as
// versões novas para lá sem perder edições do usuário:
//   - arquivo ausente na pasta do usuário → copia;
//   - arquivo igual a alguma versão já distribuída (hash no manifesto
//     relatorios-hashes.json) → substitui pela versão nova;
//   - arquivo editado (hash desconhecido) → mantém e grava a versão nova ao
//     lado como <nome>.novo<ext> (ex.: relPro001.novo.html), com aviso no log;
//   - config.json → mescla: acrescenta relatórios novos, preserva as escolhas;
//   - nunca apaga nada da pasta do usuário.
// Sem dependência do Electron: testado com node --test (electron/tests/).

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const CONFIG = 'config.json';
const TEXTO = new Set(['.html', '.htm', '.css', '.json', '.txt', '.svg']);

// Hash do conteúdo. Arquivos de texto com fim de linha normalizado (CRLF →
// LF): o mesmo modelo gravado pelo git com autocrlf, ou salvo por um editor
// que só troca os fins de linha, continua reconhecido como original.
function hashArquivo(caminho) {
  let dados = fs.readFileSync(caminho);
  if (TEXTO.has(path.extname(caminho).toLowerCase())) {
    dados = Buffer.from(dados.toString('utf8').replace(/\r\n/g, '\n'), 'utf8');
  }
  return crypto.createHash('sha256').update(dados).digest('hex');
}

// Caminhos relativos (com "/") de todos os arquivos da pasta.
function listarArquivos(raiz, sub = '') {
  const saida = [];
  for (const ent of fs.readdirSync(path.join(raiz, sub), { withFileTypes: true })) {
    const rel = sub ? `${sub}/${ent.name}` : ent.name;
    if (ent.isDirectory()) saida.push(...listarArquivos(raiz, rel));
    else if (ent.isFile()) saida.push(rel);
  }
  return saida.sort();
}

// relPro001.html → relPro001.novo.html (fora do padrão relPro001(_x)?.html
// do backend, então não aparece como variante do relatório).
function nomeNovo(rel) {
  const ext = path.posix.extname(rel);
  return `${rel.slice(0, rel.length - ext.length)}.novo${ext}`;
}

function lerManifesto(caminho) {
  try {
    const dados = JSON.parse(fs.readFileSync(caminho, 'utf8'));
    return dados && typeof dados === 'object' ? dados : {};
  } catch (_) {
    return {};
  }
}

// Acrescenta ao manifesto os hashes atuais da pasta de modelos (usado no
// build: toda versão empacotada fica registrada como "original"). Nunca
// remove hashes antigos. Devolve true se o manifesto mudou.
function registrarVersoes(origem, caminhoManifesto) {
  const manifesto = lerManifesto(caminhoManifesto);
  let mudou = false;
  for (const rel of listarArquivos(origem)) {
    if (rel === CONFIG) continue;
    const hash = hashArquivo(path.join(origem, rel));
    const lista = Array.isArray(manifesto[rel]) ? manifesto[rel] : [];
    if (!lista.includes(hash)) {
      manifesto[rel] = [...lista, hash];
      mudou = true;
    }
  }
  if (mudou) {
    const ordenado = Object.fromEntries(Object.keys(manifesto).sort().map((k) => [k, manifesto[k]]));
    fs.writeFileSync(caminhoManifesto, `${JSON.stringify(ordenado, null, 2)}\n`);
  }
  return mudou;
}

function mesclarConfig(origem, destino, log) {
  const cfgOrigem = path.join(origem, CONFIG);
  const cfgDestino = path.join(destino, CONFIG);
  if (!fs.existsSync(cfgOrigem)) return;
  if (!fs.existsSync(cfgDestino)) {
    fs.copyFileSync(cfgOrigem, cfgDestino);
    return;
  }
  let padrao, usuario;
  try {
    padrao = JSON.parse(fs.readFileSync(cfgOrigem, 'utf8'));
    usuario = JSON.parse(fs.readFileSync(cfgDestino, 'utf8'));
  } catch (e) {
    // config.json do usuário ilegível: fica como está (o backend avisa).
    log(`[relatorios] ${CONFIG} não mesclado (JSON inválido): ${e.message}`);
    return;
  }
  if (!usuario || typeof usuario !== 'object' || Array.isArray(usuario)) {
    log(`[relatorios] ${CONFIG} do usuário não é um objeto — não mesclado`);
    return;
  }
  const novos = Object.keys(padrao).filter((k) => !(k in usuario));
  if (novos.length === 0) return;
  const mesclado = { ...usuario };
  for (const k of novos) mesclado[k] = padrao[k];
  fs.writeFileSync(cfgDestino, `${JSON.stringify(mesclado, null, 2)}\n`);
  log(`[relatorios] ${CONFIG}: acrescentados ${novos.join(', ')}`);
}

// Devolve { copiados, atualizados, preservados, iguais } (listas de caminhos
// relativos) para log e testes.
function sincronizarRelatorios(origem, destino, manifesto, log = () => {}) {
  const res = { copiados: [], atualizados: [], preservados: [], iguais: [] };
  if (!fs.existsSync(origem)) {
    log(`[relatorios] modelos padrão ausentes em ${origem} — nada a sincronizar`);
    return res;
  }
  fs.mkdirSync(destino, { recursive: true });
  const conhecidos = typeof manifesto === 'string' ? lerManifesto(manifesto) : manifesto || {};

  for (const rel of listarArquivos(origem)) {
    if (rel === CONFIG) continue;
    const src = path.join(origem, rel);
    const dst = path.join(destino, rel);
    if (!fs.existsSync(dst)) {
      fs.mkdirSync(path.dirname(dst), { recursive: true });
      fs.copyFileSync(src, dst);
      res.copiados.push(rel);
      continue;
    }
    const hashNovo = hashArquivo(src);
    const hashAtual = hashArquivo(dst);
    if (hashAtual === hashNovo) {
      res.iguais.push(rel);
    } else if ((conhecidos[rel] || []).includes(hashAtual)) {
      fs.copyFileSync(src, dst);
      res.atualizados.push(rel);
    } else {
      const novo = path.join(destino, nomeNovo(rel));
      if (!fs.existsSync(novo) || hashArquivo(novo) !== hashNovo) fs.copyFileSync(src, novo);
      res.preservados.push(rel);
      log(`[relatorios] ${rel} foi editado pelo usuário — mantido; versão nova gravada em ${nomeNovo(rel)}`);
    }
  }
  mesclarConfig(origem, destino, log);
  log(
    `[relatorios] sincronizado em ${destino}: ${res.copiados.length} copiado(s), ` +
      `${res.atualizados.length} atualizado(s), ${res.preservados.length} editado(s) preservado(s), ` +
      `${res.iguais.length} sem mudança`,
  );
  return res;
}

module.exports = { sincronizarRelatorios, registrarVersoes, hashArquivo, nomeNovo };

// Build: node electron/relatorios-sync.js registrar → acrescenta ao
// manifesto os hashes da pasta relatorios/ que vai no pacote.
if (require.main === module && process.argv[2] === 'registrar') {
  const raiz = path.join(__dirname, '..');
  const mudou = registrarVersoes(path.join(raiz, 'relatorios'), path.join(__dirname, 'relatorios-hashes.json'));
  console.log(mudou ? 'relatorios-hashes.json atualizado' : 'relatorios-hashes.json já contém esta versão');
}
