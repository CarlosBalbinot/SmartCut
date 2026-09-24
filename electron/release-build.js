// item 6.1 — Build do instalador Windows ASSINADO (release).
//
// Uso: npm run dist:assinado
//
// Assinatura é OPCIONAL por design:
//   - `npm run dist`            -> build local SEM certificado (CSC_IDENTITY_AUTO_DISCOVERY=false)
//   - `npm run dist:assinado`   -> build de release; usa o certificado de código
//                                  e FALHA rápido (forceCodeSigning) se ele não existir.
//
// O certificado pode vir de duas formas (ambas são lidas, com prioridade da
// variável de ambiente já definida):
//   1. Arquivo release.env (gitignored) na raiz, ex.:
//        CSC_LINK=C:\segredos\smartcut-code-signing.pfx
//        CSC_KEY_PASSWORD=minha-senha
//        # opcional: WIN_CSC_LINK / WIN_CSC_KEY_PASSWORD também são aceitos
//   2. Variáveis de ambiente já exportadas no shell/CI (CSC_LINK/CSC_KEY_PASSWORD).
//
// Documentação completa: docs/ELECTRON.md (seção "Instalador e assinatura").
const { build, Platform, createTargets } = require('electron-builder');
const fs = require('fs');
const path = require('path');

// Carrega release.env (sem dependência externa), sem sobrescrever variáveis
// que já estejam definidas no ambiente — padrão "dotenv técnico" mínimo.
function carregarReleaseEnv() {
  const arquivo = path.join(__dirname, '..', 'release.env');
  if (!fs.existsSync(arquivo)) return;
  const linhas = fs.readFileSync(arquivo, 'utf8').split(/\r?\n/);
  for (const linha of linhas) {
    const trecho = linha.trim();
    if (!trecho || trecho.startsWith('#')) continue;
    const igual = trecho.indexOf('=');
    if (igual < 1) continue;
    const chave = trecho.slice(0, igual).trim();
    const valor = trecho.slice(igual + 1).trim().replace(/^["']|["']$/g, '');
    if (!(chave in process.env)) process.env[chave] = valor;
  }
}

carregarReleaseEnv();

// Em Windows, o electron-builder aceita WIN_CSC_LINK/WIN_CSC_KEY_PASSWORD;
// normaliza para o formato canônico CSC_LINK/CSC_KEY_PASSWORD para simplificar.
process.env.CSC_LINK = process.env.CSC_LINK || process.env.WIN_CSC_LINK || '';
process.env.CSC_KEY_PASSWORD =
  process.env.CSC_KEY_PASSWORD || process.env.WIN_CSC_KEY_PASSWORD || '';

if (!process.env.CSC_LINK) {
  console.error(
    '[release-build] Nenhum certificado de código definido (CSC_LINK/CSC_KEY_PASSWORD ou release.env).\n' +
    'Assinatura é obrigatória em build de release (forceCodeSigning).\n' +
    'Para build local SEM assinatura, use: npm run dist\n'
  );
  process.exit(1);
}

build({
  // Mesma forma que o CLI monta os alvos (--win): Map<Platform, Map<Arch, string[]>>
  // com target NSIS para a arquitetura atual.
  targets: createTargets([Platform.WINDOWS], 'nsis'),
  publish: 'never',
  config: {
    win: {
      // FALHA rápido se o certificado não puder ser aplicado — não geramos
      // instalador "achado por acaso" não assinado num build de release.
      forceCodeSigning: true,
    },
  },
}).catch((err) => {
  console.error(`[release-build] Falha no build assinado: ${err.message}`);
  process.exit(1);
});
