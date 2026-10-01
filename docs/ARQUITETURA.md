# SmartCut — Arquitetura e roadmap

Documento de referência para as próximas fases do SmartCut: para onde o
produto vai, o que no código atual ajuda ou atrapalha, as decisões já
tomadas e a ordem de execução. Como o sistema funciona **hoje**:
[SISTEMA.md](SISTEMA.md). Regras para agentes de código:
[CLAUDE.md](CLAUDE.md).

Consulte este documento antes de qualquer mudança estrutural (banco,
instalação, módulos, autenticação, API, idiomas).

Esforço: **P** = até 1 semana · **M** = 1 a 3 semanas · **G** = mais de 3
semanas (1 dev). Levantamento feito na versão 1.3.0 (outubro/2026).

## Sumário

1. [Visão do produto](#1-visão-do-produto)
2. [Situação atual](#2-situação-atual)
3. [Diagnóstico](#3-diagnóstico)
   - [3.1 PostgreSQL](#31-postgresql--g)
   - [3.2 Modo servidor](#32-modo-servidor--g)
   - [3.3 Módulos](#33-módulos)
   - [3.4 API de integração](#34-api-de-integração--mg)
   - [3.5 Idiomas](#35-idiomas--g)
   - [3.6 Edição Brasil x internacional](#36-edição-brasil-x-internacional--m)
4. [Riscos](#4-riscos)
5. [Decisões tomadas](#5-decisões-tomadas)
6. [Roadmap](#6-roadmap)
7. [Como trabalhamos em cada fase](#7-como-trabalhamos-em-cada-fase)

---

## 1. Visão do produto

- **ERP instalado na empresa do cliente**: uma máquina **servidor** (backend
  + PostgreSQL) e várias **estações** (o aplicativo Electron) usando ao mesmo
  tempo pela rede local. **Sem versão web**: na nuvem ficam só as licenças e
  as atualizações.
- **Módulos vendidos por licença**:

  | Módulo | Edição |
  |---|---|
  | Núcleo (usuários, configurações, login, relatórios) | Todas |
  | Cadastros (clientes, transportadoras, produtos e grades) | Todas |
  | Moldes | Todas |
  | Corte (OC, encaixe, ficha de corte, tecidos e lotes) | Todas |
  | Vendas (pedidos, tabelas de preço, vendedores, painel do vendedor) | Brasil |
  | Estoque | Todas (escopo por edição, ver seção 5) |
  | Fiscal — NF-e, TES, certificado A1 | Só Brasil |
  | Financeiro — contas, fluxo de caixa, contabilidade | Só Brasil |
  | Gestão — precificação (Simples Nacional), projeção | Só Brasil |

- **Edições**:
  - **Brasil**: o ERP completo.
  - **Internacional**: Corte e Moldes (com Núcleo, Cadastros e o estoque de
    tecidos), integrados ao ERP do cliente pela API de integração.
- **Idiomas**: pt, it, en, es **só** no Núcleo, Cadastros, Corte, Moldes e
  relatórios de corte. Fiscal, Financeiro e Gestão ficam só em português.

---

## 2. Situação atual

### O que já ajuda

- O ORM (SQLAlchemy 2) é quase todo portável; o índice parcial da OC já tem
  `postgresql_where`; `ilike` já é usado nas buscas.
- Os arquivos do usuário já passam por **HTTP autenticado**
  (`routers/uploads.py`, upload de moldes, logo, anexos), então as estações
  não precisam de pasta compartilhada.
- Permissões por módulo já existem no backend (`require_permission`,
  `MODULOS_VALIDOS`) e no menu (`App.jsx`, `hasPermission`) — o gancho
  natural para a licença.
- Os routers já são agrupados por domínio em `REGISTRO_DE_ROUTERS`
  (`main.py`).
- A OC já guarda cópia dos itens do pedido (`itens_ordem_corte`), o que
  facilita a OC sem pedido de venda.
- A numeração de item do pedido já usa o padrão certo (UPDATE atômico no
  contador).

### Pontos críticos

- **Numerações** por MAX+1 ou contador lido e regravado em Python —
  inclusive a da **NF-e** (número duplicado é rejeitado pela SEFAZ).
- **Estoque e status da OC**: as transições verificam e depois gravam, sem
  trava; com dois usuários, o mesmo lote pode ser baixado duas vezes.
- **Edição simultânea**: vale a última gravação, sem aviso.
- **Corte preso a Vendas**: chave estrangeira obrigatória para
  `pedidos_venda`, configuração de produção dentro da tabela da precificação,
  ficha de corte importando código de Fiscal e Vendas.
- **Motor de encaixe**: fila em memória e um job por vez no processo
  inteiro.
- **Segredos** (JWT, chave do certificado) gerados pelo Electron com DPAPI
  do usuário — não servem para um backend rodando como serviço.
- **Textos**: o motivo da decisão de enfesto fica gravado no banco como
  texto em português; formatação `pt-BR` e `R$` fixos nas telas.

---

## 3. Diagnóstico

### 3.1 PostgreSQL — **G**

#### Código específico do SQLite

| Ponto | Onde | Esforço |
|---|---|---|
| `render_as_batch=True` fixo | `alembic/env.py`; as 13 migrations usam `batch_alter_table` | P — condicional ao dialeto; a baseline nova não usa as antigas |
| `check_same_thread` | `database.py`, já condicional | — |
| `func.strftime` (6 usos) | `routers/financeiro.py` (4), `routers/pedidos_venda.py` (2) | P — `to_char`/`extract` ou chave montada em Python |
| PRAGMA e cópia do `.db` | `services/backup_service.py`, `scripts/backup_sqlite.py`, `scripts/montar_banco_producao.py` | M — backup vira `pg_dump` |
| LIKE / ILIKE | `.ilike` (13 usos), `func.lower` (3) | — no Postgres o ILIKE diferencia acento; usar `unaccent` se a busca precisar ignorar |
| JSON | 6 colunas `JSON` (molde, encaixe, OC, produto) | P — funciona igual; opcional `JSONB` |
| UUID | `Uuid(as_uuid=True)` em ~79 colunas; no SQLite é texto hex de 32 caracteres | Só na migração de dados |
| Booleanos | 23 colunas; 0/1 no SQLite | Só na migração de dados |
| Datas | Mistura de `DateTime` sem fuso com `datetime.utcnow`, 38 colunas `timezone=True` e `datetime.now()` sem fuso. No Postgres, `timestamptz` volta com fuso e comparar com data sem fuso gera `TypeError` | P–M — padronizar com fuso, em UTC |
| `Float` (21 colunas) | Pesos e metros | Funciona; avaliar `Numeric` onde há soma de estoque |
| Testes | `tests/conftest.py` usa `sqlite://` em memória (253 testes) | M — suíte rodando em Postgres |

#### Numerações e disputas de concorrência

| Número / operação | Implementação | Risco com vários usuários |
|---|---|---|
| **NF-e e NFC-e** | `nfe_service.proximo_numero`: `empresa.nfe_numero_atual += 1` em Python | **Alto** — dois usuários pegam o mesmo número |
| Pedido | `venda_service.proximo_numero`: MAX + 1, UNIQUE, sem nova tentativa | Erro 500 na colisão |
| OC | `ordem_corte_service`: MAX + 1, UNIQUE, sem nova tentativa | Erro 500 na colisão |
| Encaixe (ENC) | `nesting_service._numerar`: MAX + 1 com 3 tentativas | Aceitável |
| Item do pedido | UPDATE atômico no contador | ✅ padrão certo |
| Códigos de cliente, grupo, produto, sequência de SKU | Leem todos os códigos e calculam o maior em Python (`routers/clientes.py`, `grupo_produto_service`, `produto_service`, `grade_service`) | Erro de UNIQUE |
| **Transições da OC e estoque** | `enviar_a_producao`, `concluir`, `reabrir` verificam o status e depois gravam; `lote_service.debitar`/`creditar` fazem a conta em Python | **Alto** — baixa dupla do lote |

Correção (**M**): tabela `sequencias(nome, valor)` com
`UPDATE … SET valor = valor + 1 RETURNING valor` (funciona nos dois bancos).
Transições com `SELECT … FOR UPDATE` ou `UPDATE … WHERE status = :esperado`
conferindo as linhas afetadas. Estoque com
`UPDATE lotes SET peso = peso - :kg` direto no SQL.

#### Migração de dados e das migrations — **M**

- **Baseline nova só para Postgres** ("2.0" = retrato da head atual). A
  cadeia antiga fica só para o SQLite 1.x; para migrar, a instalação precisa
  estar na última 1.x.
- Script SQLite → Postgres:
  1. ler pelo SQLAlchemy (converte UUID hex, 0/1, Decimal e JSON);
  2. copiar na ordem das chaves estrangeiras;
  3. ajustar as sequências dos IDs inteiros (`setval`);
  4. validar contagens e somas (estoque por lote, saldos), reaproveitando o
     relatório do `montar_banco_producao.py`;
  5. rodar sempre numa cópia do banco.

#### PostgreSQL no instalador do servidor — **M**

- **Binários em zip** (EDB, PG 17) dentro do instalador; no primeiro uso,
  `initdb` com usuário próprio e `pg_ctl register -N SmartCutDB -S auto`
  (serviço do Windows). Sem o instalador interativo da EDB.
- **Porta 5433** (configurável) e `listen_addresses='localhost'`: as
  estações falam com a **API**, nunca com o banco.
- Senha aleatória gerada na instalação, guardada com DPAPI **da máquina**;
  autenticação `scram-sha-256`.
- Backup: `pg_dump -Fc` agendado pelo backend, mantendo N cópias, junto com
  `uploads/`. Restauração pelas Configurações ou por script.
- Instalador ~100 MB maior; ~300 MB instalado.

### 3.2 Modo servidor — **G**

#### Electron como estação — **M**

Endereços fixos em 127.0.0.1 hoje: `electron/backend.js` (`/health`),
`main.js` (CSP `connect-src`/`img-src` e `BACKEND_URL` do PDF), `apiUrl` do
preload e `server.py` (`host="127.0.0.1"`).

- Endereço do servidor em `userData/servidor.json`, com tela "Conectar ao
  servidor" na primeira abertura.
- **Descoberta na rede** por broadcast UDP numa porta fixa (o servidor
  responde nome, versão e porta), sem dependência nova. Alternativa: mDNS
  com `zeroconf`.
- CSP montada a partir do endereço configurado.
- Na estação, `spawnBackend` não roda.
- Instalador NSIS com dois componentes: **Servidor** (backend, Postgres e,
  opcionalmente, o app) e **Estação** (só o app).
- **Versão**: `/health` devolve a versão; estação com versão diferente se
  recusa a abrir ou se atualiza.
- **TLS** (**M**): sem ele, JWT e senhas trafegam abertos na LAN. HTTPS com
  certificado autoassinado gerado na instalação; a estação fixa a impressão
  digital na primeira conexão.
- Login, token com DPAPI na estação e CORS (`app://bundle`) continuam
  valendo.

#### Backend como serviço do Windows — **M**

- Exe do PyInstaller como serviço (WinSW ou NSSM), reinício automático em
  falha e regra de firewall da porta.
- **Segredos mudam de dono**: o segredo JWT e o `SMARTCUT_CERT_KEY` passam a
  ser gerados pelo instalador do servidor, com DPAPI da máquina ou arquivo
  com permissão restrita à conta do serviço.
- A sincronização dos relatórios (`relatorios-sync.js`) passa do Electron
  para o boot do servidor.
- Tokens revogados e limite de tentativas de login ficam em memória —
  corretos **desde que o backend rode num único processo** (sem vários
  workers do uvicorn).

#### Fila do motor de encaixe — **M**

Hoje (`services/nesting_jobs.py`): fila em memória, uma thread para o
processo inteiro, `_UM_POR_VEZ` com 2 threads do spyrrow. Reiniciar perde a
fila; com vários usuários, quem chega espera o job inteiro do outro (até
300 s por OC).

- Tabela `jobs_encaixe` (estado, progresso, usuário, tempos). No boot, o que
  estava RODANDO vira ERRO "interrompido".
- Motor em **processo filho**: estouro de memória não derruba a API, e
  cancelar encerra o processo de verdade.
- Jobs simultâneos configurável (padrão 1; 2 em servidor com 8+ núcleos e
  16+ GB).
- Posição na fila e estimativa de tempo na tela (`planejamento/custo.py`).
- Documentar requisito mínimo do servidor.

#### Edição simultânea — **M–G**

Vale a última gravação, sem aviso, em: pedido (`PUT/PATCH` e `PUT …/itens`,
que substitui todos os itens), OC (`PUT` e `/tecidos`), produtos/SKUs/preços,
moldes e o editor de geometria, lotes de tecido, configurações. A OC tem
`atualizado_em`, mas ele não é conferido.

- Coluna `versao` com `version_id_col` do SQLAlchemy; o frontend envia a
  versão no PUT; se outro usuário gravou antes, **409** "registro alterado
  por outro usuário, recarregue".
- Alterar uma coleção filha (itens, tecidos) incrementa a versão do pai.
- Prioridade: pedido, OC, molde, produto, lote, configurações.

#### Arquivos do usuário — **P** (exceto modelos de relatório)

- Anexos, logo, moldes, NF-e e catálogos já passam pela API. No servidor, a
  pasta de dados vira `C:\ProgramData\SmartCut\`.
- Certificado A1 e assinatura da NF-e já ficam no backend.
- **Modelos de relatório** hoje são editados como arquivo: upload/download
  pela tela (P–M) ou pasta compartilhada no servidor.
- O PDF continua sendo gerado na estação (`printToPDF`) a partir do HTML do
  servidor.

### 3.3 Módulos

#### Mapa atual do código

| Módulo | Backend (routers / services / models) | Telas |
|---|---|---|
| **Núcleo** | auth, usuarios, uploads, relatorios (engine), dashboard, configuracao_empresa, configuracao_grade, tabelas_grade · `Empresa`, `Usuario`/`Permissao` | Login, Usuários, Configurações, Dashboard |
| **Cadastros** | clientes, transportadoras, produtos (+ grupos e grade), SKUs | Clientes, Transportadoras, Produtos, Grade |
| **Moldes** | moldes, grupos_molde, `parsers/` (PLT, DXF, ADS), molde_service | Moldes, importação, seta do fio |
| **Corte** | ordens_corte, encaixes, modelos/cores/lotes de tecido, nesting_service, nesting_v2, planejamento, plano_enfesto, relPro001 | OCs, Encaixe Rápido, Encaixes, Tecidos |
| **Vendas** | pedidos_venda, tabelas_preco, grupos_preco, condicoes_pagamento, vendedores, vendedor_painel, catalogos, leads, relVen001 | Pedidos, Tabelas de preço, Vendedores, `/vendedor` |
| **Fiscal** (BR) | tes, nfe, nfe_service, danfe_service | NF-e, TES, Config. fiscais |
| **Financeiro** (BR) | financeiro, contabilidade_service | `pages/financeiro/*` |
| **Gestão** (BR) | precificacoes, projeção | Precificação, Projeção |
| **Estoque** | Não existe como módulo: hoje é só o estoque de lotes de tecido, dentro do Corte | — |

#### Dependências que impedem o Corte de funcionar sozinho

1. `OrdemCorte.pedido_id` é chave estrangeira **obrigatória** para
   `pedidos_venda`; `Encaixe.pedido_id` também aponta para lá.
2. O Encaixe Rápido **cria um pedido de venda mínimo**.
3. A ficha de corte (`dados_ordem_corte`) importa `dados_pedido`, que
   importa `nfe_service`, `venda_service` e `condicao_service`.
4. A configuração de produção (mesa, tempo limite, tolerância) está em
   `ConfiguracaoEmpresa`, na mesma tabela da `aliquota_simples`, lida via
   `precificacao_service.get_ou_criar_config`.
5. `molde_service` consulta `ItemPedido` antes de excluir um molde.
6. As OCs usam a permissão `"encaixes"`, sem permissão própria.

#### Corte e Moldes sem Vendas, Fiscal e Financeiro — **G**

- Origem genérica da demanda: `OrdemCorte.pedido_id` aceita vazio e entram
  `origem` (`PEDIDO_VENDA` | `EXTERNO` | `RAPIDO`) e `referencia_externa`.
  Cadastro e edição de OC sem pedido. O Encaixe Rápido deixa de criar pedido
  de venda.
- `ConfiguracaoProducao` separada de `ConfiguracaoEmpresa` (migration move
  as colunas).
- Ficha de corte lê a empresa do Núcleo, sem importar Fiscal nem Vendas.
- Revisar os usos de pedido em `nesting_service` (~36) e
  `ordem_corte_service` (~58).

#### Licença liga e desliga módulos — **M**

- Arquivo de licença assinado (Ed25519) pelo servidor de licenças na nuvem:
  edição, módulos, validade, identificação do servidor, número de estações.
  Validação no boot e online periódica, com prazo de tolerância sem
  internet.
- **Backend**: cada grupo do `REGISTRO_DE_ROUTERS` ganha um módulo de
  licença; grupo não licenciado não é registrado (ou responde 403 "módulo
  não licenciado"). Tabela liga módulo de licença aos módulos de permissão.
- **Telas**: `GET /api/v1/licenca` devolve os módulos; o menu filtra por
  licença **e** por `hasPermission`.
- Número de estações: sessões ativas por máquina no servidor.

### 3.4 API de integração — **M–G**

Depende de 3.3 (OC sem pedido de venda).

**O que já existe**: tudo em `/api/v1`, com OpenAPI automático e respostas
`{data, error}` — mas feito para as telas (login de usuário, formatos
internos), sem contrato estável.

**O que falta**:

- **Autenticação de sistema externo**: tabela `chaves_integracao` (hash da
  chave, escopos, módulo licenciado); header `X-API-Key` ou client-credentials
  gerando JWT; auditoria e limite de requisições.
- Prefixo próprio e versionado: `/api/integracao/v1`, com documentação
  própria.
- **Entrada**:
  - `PUT produtos/{codigo_externo}` — upsert com grade de cores e tamanhos e
    vínculo ao grupo de molde;
  - `POST pedidos-corte` — `id_externo` para não duplicar, itens
    produto/cor/tamanho/quantidade, data; gera a OC com `origem=EXTERNO`;
  - `PUT tecidos` e `PUT lotes` — cadastro de tecidos e lotes vindo do ERP
    externo (decisão da seção 5).
- **Saída**:
  - `GET pedidos-corte/{id_externo}` — status da OC;
  - `GET …/ficha` — PDF e JSON das mesas;
  - `GET …/consumo` — kg e metros por lote e tecido, planejado e real, custo;
  - depois: webhooks na conclusão da OC.

### 3.5 Idiomas — **G**

Escopo: Núcleo, Cadastros, Corte, Moldes e relatórios de corte.

#### Volume aproximado (varredura heurística)

| Parte | Quantidade |
|---|---|
| Telas — Núcleo | ~250 textos (25 arquivos) |
| Telas — Cadastros | ~360 |
| Telas — Corte | ~370 |
| Telas — Moldes | ~50 a 100 |
| **Total das telas** | **~1.000 a 1.100** |
| Backend no escopo (erros e mensagens) | ~290 pontos |
| Ficha de corte (relPro001 e básico) | ~40 |
| Electron (menus, diálogos, loading) e instalador NSIS (hoje só `pt_BR`) | ~15 |

#### Estratégia

- **React: i18next + react-i18next**, arquivos por módulo (`nucleo`,
  `corte`, `moldes`), JSON por idioma, carregamento sob demanda, `Intl` para
  formatação.
- **Backend devolve código e parâmetros**:
  `{"error": {"codigo": "OC_STATUS_INVALIDO", "params": {...}, "mensagem": "<pt>"}}`
  — a mensagem em português é o fallback (e o que Fiscal e Financeiro
  continuam usando).
- **`decisao_enfesto`**: hoje o `motivo` é texto pronto
  (`nesting_v2/decisor.py`). Muda para lista de `{codigo, params}`; OCs
  antigas mantêm o texto em português como fallback.
- **Relatórios**: função `t('chave')` no Jinja, com dicionários em
  `relatorios/_i18n/<idioma>.json` — o modelo editável continua sendo um só.
  Idioma do documento: o da empresa ou o do usuário que imprime.

#### Formatos

- ~50 usos de `pt-BR` fixo e 52 de `R$` em 38 arquivos: centralizar em
  `utils/formato.js` (data, número, moeda) com locale e moeda da empresa.
- **Unidades**: o banco continua métrico (`largura_cm`,
  `comprimento_max_mesa_cm`, `peso_kg`, gramatura em g/m²). Polegada/jarda,
  libra e oz/yd² só na exibição e na digitação, por preferência da empresa
  (**M**). Conferir a unidade assumida pelos parsers de DXF e PLT.

### 3.6 Edição Brasil x internacional — **M**

Depois de 3.3. **Um único esquema de banco** para as duas edições: a edição
só define quais routers e menus são registrados; as tabelas exclusivas do
Brasil existem e ficam vazias.

**Exclusivo da edição Brasil**: Fiscal (tes, nfe, danfe, certificado),
Financeiro e contabilidade, Gestão (precificação e projeção, que dependem de
`aliquota_simples`/Simples Nacional).

**Campos com regra brasileira fora do fiscal**:

| Onde | Campos | Proposta |
|---|---|---|
| `Empresa` (`models/venda.py`) | `cnpj`, `ie`, `codigo_ibge_municipio`, `codigo_pais="1058"`, `cep`, e campos fiscais misturados: `regime_tributario`, `uf_emitente="RS"`, `ambiente_sefaz`, `certificado_*`, séries e números de NF | Separar `Empresa` (nome, `documento_fiscal` genérico, país, endereço) de `EmpresaFiscalBR` (**M**) |
| `Cliente`, `Transportadora` | `cnpj`, `cpf`, `ie`, `inscricao_municipal`, `rg`, `estado String(2)`, `cep String(9)`, IBGE, `codigo_pais` | Já são opcionais (nenhum CNPJ obrigatório). Generalizar: `pais` ISO-2, `tipo_documento` + `documento`, `regiao` maior que 2 caracteres, `codigo_postal`. Máscaras, ViaCEP (`utils/cepIbge.js`) e IBGE só quando o país for BR (**M**) |
| Cópia do cliente no pedido (`models/pedido.py`) | Os mesmos campos | Acompanha o cliente (módulo Vendas, só BR) |
| `ConfiguracaoEmpresa` | `aliquota_simples` junto da configuração de produção | Separar (ver 3.3) |
| Telas | `R$`, `pt-BR`, máscaras de CNPJ/CPF | Formatação central (ver 3.5) |

---

## 4. Riscos

1. **Bugs de concorrência que o SQLite escondia** (ele serializa as
   gravações e hoje há um usuário só). Os mais graves: número da NF-e e
   baixa de estoque.
2. **Contas e segredos**: o DPAPI do usuário não serve para o serviço do
   Windows; errar faz o servidor perder o JWT ou a chave do certificado.
3. **Postgres embarcado**: colisão com outro Postgres, antivírus bloqueando
   o `initdb`, instalação sem permissão de administrador.
4. **Motor de encaixe num servidor fraco**: CPU e memória divididas entre os
   usuários. Exige requisito mínimo e fila com posição.
5. **Migração dos dados reais da Vaidosa**: sempre em cópia, com validação
   de somas antes de virar a chave.
6. **Segurança na LAN**: sem TLS, o login trafega aberto.
7. **i18n crescer de escopo**: telas compartilhadas (Configurações,
   Clientes) misturam partes traduzidas e partes só em português.
8. **Licença sem internet**: definir o prazo de tolerância e o que acontece
   quando vence.
9. **Testes só em SQLite** hoje.

---

## 5. Decisões tomadas

| Tema | Decisão |
|---|---|
| Banco | **Só PostgreSQL**, inclusive no Corte avulso de um PC: servidor e estação na mesma máquina. Um único dialeto e uma única suíte de testes. O SQLite fica só na linha 1.x. |
| Estoque | No **Corte**: tecidos e lotes. No **ERP completo**: também aviamentos/insumos e produto acabado por cor e tamanho. |
| Painel do vendedor | Mantido, acessível **só dentro da rede local**. |
| Corte avulso | Cadastro próprio de tecidos e lotes; o ERP externo também pode enviá-los pela API. |
| Fiscal, Financeiro e Gestão | Exclusivos da **edição Brasil**. Ficam só em português. |
| Web | Sem versão web nem SaaS. Na nuvem, só licenças e atualizações. |

---

## 6. Roadmap

Cada fase entrega valor sozinha.

| Fase | Conteúdo | Valor entregue | Esforço |
|---|---|---|---|
| **F0 — Robustez no SQLite** | Sequências atômicas (NF-e primeiro), trava nas transições da OC e na baixa de estoque, coluna `versao` com 409, datas com fuso, erro com `codigo` e `params` | Fecha bugs reais já na 1.x e prepara o resto | M |
| **Fase 5 — NF-e autorizada gera parcelas no financeiro** | Ao autorizar a NF-e, gerar a venda financeira e as parcelas pela condição de pagamento | Fecha o fluxo Pedido → NF-e → Financeiro | — |
| **F1 — PostgreSQL num servidor só** | Baseline nova, Postgres embarcado como serviço, backend como serviço, segredos na máquina, `pg_dump`, migração de dados, testes em Postgres | Banco robusto, backup de verdade, "tudo num PC" | G |
| **F2 — Vários usuários na rede** | Electron estação (endereço, descoberta, CSP dinâmica, checagem de versão), TLS, fila persistente em processo separado, modelos de relatório pela tela | ERP multiusuário | G |
| **F3 — Módulos, licença e edições** | Corte sem pedido de venda, separar Empresa / Configuração de Produção / Fiscal, licença assinada, routers e menus por licença, edição BR/internacional, cadastros com país, módulo Estoque | Venda modular; Corte avulso | G |
| **F4 — API de integração** | Chaves de API, `/api/integracao/v1`, produtos, pedidos de corte, tecidos e lotes de entrada; ficha e consumo de saída | Corte e Moldes integrados ao ERP do cliente | M–G |
| **F5 — Idiomas** | i18next, ~1.100 textos, códigos no backend e no decisor, relatórios com `t()`, unidades imperiais, instalador multilíngue | Edição internacional | G |

A infraestrutura de i18n (biblioteca e formatação central) pode começar junto
com F1/F2; a tradução de verdade fica para depois de F3, que mexe nas mesmas
telas.

### Acompanhamento

Atualizar ao fim de cada fase.

| Fase | Conteúdo | Status | Branch | Versão |
|---|---|---|---|---|
| F0 | Robustez no SQLite | PENDENTE | — | — |
| Fase 5 | NF-e autorizada gera parcelas no financeiro | PENDENTE | — | — |
| F1 | PostgreSQL num servidor só | PENDENTE | — | — |
| F2 | Vários usuários na rede | PENDENTE | — | — |
| F3 | Módulos, licença e edições | PENDENTE | — | — |
| F4 | API de integração | PENDENTE | — | — |
| F5 | Idiomas | PENDENTE | — | — |

Status: `PENDENTE` · `EM ANDAMENTO` · `CONCLUÍDA`.

---

## 7. Como trabalhamos em cada fase

1. **Branch própria** a partir do `master` (ex.: `f0-robustez`); marcar a
   fase como `EM ANDAMENTO` na tabela, com o nome da branch.
2. **Plano antes do código**: o que muda, arquivos afetados, migrations,
   riscos e como testar — revisado antes de começar.
3. **Passos curtos com revisão**: cada passo é pequeno, revisado e
   commitado antes do próximo.
4. **Testes**: os da fase junto com o código; antes do merge, `ruff` e
   pytest no backend, `npm run lint`, `npm test` e `npm run build` no
   frontend (ver [CLAUDE.md](CLAUDE.md)). Dados reais só em cópia do banco.
5. **Merge** no `master` com a fase completa e os testes passando.
6. **Release**: versão nova, instalador e notas.
7. **Atualizar este documento**: status `CONCLUÍDA` e versão na tabela de
   acompanhamento; ajustar o diagnóstico se algo mudou. Atualizar também o
   [SISTEMA.md](SISTEMA.md) com o que passou a funcionar diferente.
