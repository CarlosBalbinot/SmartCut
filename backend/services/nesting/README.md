# `services/nesting` — engine de encaixe (bundle de terceiros)

Esta pasta contém o bundle **vendido** da biblioteca de nesting usada
historicamente pelo SmartCut (helpers JS + artefatos de build de um addon C++
[node-gyp]). Ela **não é gerada nem consumida pelo runtime atual** do backend.

## O runtime de nesting usado de verdade

O encaixe em produção roda em **JavaScript puro**:

- `backend/nesting/nest_worker.js` — packer *skyline bottom-left*, lê um job
  JSON via stdin e devolve posicionamentos via stdout (sem dependência de binário).
- `backend/nesting/svgnest/` — lib SVGNest (terceiros), **não versionada** no
  git, apenas empacotada no build.

O empacotamento no executável é feito pelo `backend/smartcut.spec` via `datas`
(ver `all_datas`):

```python
('nesting/nest_worker.js', 'nesting'),
('nesting/svgnest',        'nesting/svgnest'),
```

## `engine/` — artefatos de build (NÃO versionados)

`engine/` contém apenas **saídas de build** de um addon node-gyp (C++) de um
bundle antigo:

- `Release/` — binário `addon.node`, objetos `.o` e dependências `.d`;
- scaffolding gerado pelo node-gyp — `Makefile`, `binding.Makefile`,
  `*.target.mk`, `config.gypi`, `gyp-mac-tool`.

Nenhum desses arquivos é usado pelo runtime (o `nest_worker.js` atual não faz
`require()` de addon) e **nenhum deles é versionado** (item 10.1 do
`docs/PROMPT-CORRECOES.md`). A pasta inteira está no `.gitignore`:

```
backend/services/nesting/engine/
```

### Como (re)gerar o artefato, se o addon for um dia reintroduzido

O addon não tem fontes no repositório (estavam fora do survey inicial). Para
recriar o binário a partir do upstream desse bundle:

1. restaure as fontes C++ (`addon.cc`, `minkowski.cc`) e o `binding.gyp` no
   local original do node-gyp;
2. na pasta do engine, rode `node-gyp rebuild` (gera `Release/addon.node`,
   `.o`/`.d` e os scaffolding listados acima — que permanecem ignorados);
3. se o runtime passar a consumir o addon, ele deve ser incluído no
   `smartcut.spec` — seja via `binaries` (arquivo `.node`) seja via `datas` —
   nunca commitado como binário no git.