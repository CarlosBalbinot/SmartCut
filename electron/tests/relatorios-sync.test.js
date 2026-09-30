// Sincronização relatorios-padrao → pasta do usuário (electron/relatorios-sync.js).
// Rodar: npm run test:electron
const { test, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { sincronizarRelatorios, registrarVersoes, hashArquivo } = require('../relatorios-sync.js');

let tmp, origem, destino, manifesto;

function escrever(raiz, rel, conteudo) {
  const p = path.join(raiz, rel);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, conteudo);
}
const ler = (raiz, rel) => fs.readFileSync(path.join(raiz, rel), 'utf8');
const existe = (raiz, rel) => fs.existsSync(path.join(raiz, rel));

// Pacote "v1" registrado no manifesto e depois atualizado para "v2" (também
// registrado, como faz o build).
function pacote(versao) {
  escrever(origem, 'vendas/relVen001.html', `<p>venda ${versao}</p>`);
  escrever(origem, 'producao/relPro001.html', `<p>producao ${versao}</p>`);
  escrever(origem, 'producao/relPro001_basico.html', `<p>basico ${versao}</p>`);
  escrever(origem, '_comum/cabecalho_empresa.html', `<header>${versao}</header>`);
  escrever(origem, 'assets/logo.png', Buffer.from([0x89, 0x50, 0x4e, 0x47, versao === 'v1' ? 1 : 2]));
  escrever(
    origem,
    'config.json',
    JSON.stringify({ relVen001: { padrao: 'relVen001.html' }, relPro001: { padrao: 'relPro001.html' } }),
  );
  registrarVersoes(origem, manifesto);
}

beforeEach(() => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'smartcut-rel-'));
  origem = path.join(tmp, 'relatorios-padrao');
  destino = path.join(tmp, 'usuario', 'relatorios');
  manifesto = path.join(tmp, 'relatorios-hashes.json');
});

afterEach(() => fs.rmSync(tmp, { recursive: true, force: true }));

test('(a) pasta do usuário vazia: copia tudo, inclusive config.json e assets', () => {
  pacote('v1');
  const res = sincronizarRelatorios(origem, destino, manifesto);
  for (const rel of [
    'vendas/relVen001.html',
    'producao/relPro001.html',
    'producao/relPro001_basico.html',
    '_comum/cabecalho_empresa.html',
    'assets/logo.png',
    'config.json',
  ]) {
    assert.ok(existe(destino, rel), rel);
  }
  assert.equal(res.copiados.length, 5);
  assert.deepEqual(JSON.parse(ler(destino, 'config.json')), JSON.parse(ler(origem, 'config.json')));
});

test('(b) modelo original de versão antiga é substituído pela versão nova', () => {
  pacote('v1');
  sincronizarRelatorios(origem, destino, manifesto);
  pacote('v2');
  const res = sincronizarRelatorios(origem, destino, manifesto);
  assert.equal(ler(destino, 'producao/relPro001.html'), '<p>producao v2</p>');
  assert.equal(res.atualizados.length, 5);
  assert.equal(res.preservados.length, 0);
  assert.ok(!existe(destino, 'producao/relPro001.novo.html'));
});

test('(b) original antigo com fim de linha CRLF continua reconhecido', () => {
  pacote('v1');
  escrever(origem, 'vendas/relVen001.html', '<p>\nvenda v1\n</p>\n');
  registrarVersoes(origem, manifesto);
  sincronizarRelatorios(origem, destino, manifesto);
  escrever(destino, 'vendas/relVen001.html', '<p>\r\nvenda v1\r\n</p>\r\n');
  pacote('v2');
  sincronizarRelatorios(origem, destino, manifesto);
  assert.equal(ler(destino, 'vendas/relVen001.html'), '<p>venda v2</p>');
});

test('(c) modelo editado pelo usuário é mantido e a versão nova vai para .novo', () => {
  pacote('v1');
  sincronizarRelatorios(origem, destino, manifesto);
  escrever(destino, 'producao/relPro001.html', '<p>minha versao</p>');
  escrever(destino, 'assets/logo.png', 'logo da empresa');
  escrever(destino, 'vendas/relVen001_meu.html', '<p>variante do usuario</p>');
  pacote('v2');
  const logs = [];
  const res = sincronizarRelatorios(origem, destino, manifesto, (m) => logs.push(m));

  assert.equal(ler(destino, 'producao/relPro001.html'), '<p>minha versao</p>');
  assert.equal(ler(destino, 'producao/relPro001.novo.html'), '<p>producao v2</p>');
  assert.equal(ler(destino, 'assets/logo.png'), 'logo da empresa');
  assert.ok(existe(destino, 'assets/logo.novo.png'));
  assert.deepEqual(res.preservados.sort(), ['assets/logo.png', 'producao/relPro001.html']);
  assert.ok(logs.some((m) => m.includes('producao/relPro001.html foi editado')));
  // Os demais (não editados) foram atualizados; nada do usuário foi apagado.
  assert.equal(ler(destino, 'vendas/relVen001.html'), '<p>venda v2</p>');
  assert.equal(ler(destino, 'vendas/relVen001_meu.html'), '<p>variante do usuario</p>');
});

test('(c) sem mudança de versão, editado não gera .novo repetido e nada muda', () => {
  pacote('v1');
  sincronizarRelatorios(origem, destino, manifesto);
  escrever(destino, 'producao/relPro001.html', '<p>minha versao</p>');
  sincronizarRelatorios(origem, destino, manifesto);
  const antes = hashArquivo(path.join(destino, 'producao/relPro001.novo.html'));
  sincronizarRelatorios(origem, destino, manifesto);
  assert.equal(hashArquivo(path.join(destino, 'producao/relPro001.novo.html')), antes);
  assert.equal(ler(destino, 'producao/relPro001.html'), '<p>minha versao</p>');
});

test('(d) config.json: preserva escolhas do usuário e acrescenta relatórios novos', () => {
  pacote('v1');
  sincronizarRelatorios(origem, destino, manifesto);
  escrever(
    destino,
    'config.json',
    JSON.stringify({ relPro001: { padrao: 'relPro001_basico.html' }, relVen001: { padrao: 'relVen001_meu.html' } }),
  );
  escrever(
    origem,
    'config.json',
    JSON.stringify({
      relVen001: { padrao: 'relVen001.html' },
      relPro001: { padrao: 'relPro001.html' },
      relPro002: { padrao: 'relPro002.html' },
    }),
  );
  sincronizarRelatorios(origem, destino, manifesto);
  assert.deepEqual(JSON.parse(ler(destino, 'config.json')), {
    relPro001: { padrao: 'relPro001_basico.html' },
    relVen001: { padrao: 'relVen001_meu.html' },
    relPro002: { padrao: 'relPro002.html' },
  });
});

test('(d) config.json do usuário inválido fica intacto', () => {
  pacote('v1');
  sincronizarRelatorios(origem, destino, manifesto);
  escrever(destino, 'config.json', '{ quebrado');
  sincronizarRelatorios(origem, destino, manifesto);
  assert.equal(ler(destino, 'config.json'), '{ quebrado');
});

test('registrarVersoes acumula hashes sem apagar os antigos', () => {
  pacote('v1');
  pacote('v2');
  const m = JSON.parse(fs.readFileSync(manifesto, 'utf8'));
  assert.equal(m['producao/relPro001.html'].length, 2);
  assert.equal(m['config.json'], undefined);
  assert.equal(registrarVersoes(origem, manifesto), false);
});
