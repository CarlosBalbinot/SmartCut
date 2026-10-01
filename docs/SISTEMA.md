# SmartCut — Como o sistema funciona

Documento central do SmartCut. Explica, para quem nunca viu o projeto, o que o
sistema faz, como as partes conversam e onde fica cada coisa. Para montar o
ambiente, rodar testes e gerar o instalador, veja
[DESENVOLVIMENTO.md](DESENVOLVIMENTO.md). Regras para agentes de código estão
em [CLAUDE.md](CLAUDE.md).

O SmartCut é um sistema de gestão para confecção (hoje usado pela Vaidosa
Fitness, Guaporé/RS): cadastros de tecidos, moldes e produtos, pedidos de
venda, **planejamento do corte com encaixe automático**, nota fiscal
eletrônica, financeiro e um painel para os vendedores.

O SmartCut é **somente desktop**: tudo roda instalado na máquina do cliente
(aplicativo, backend, banco e arquivos). **Não haverá versão web nem SaaS.**

---

## a. Arquitetura

```
┌───────────────────────────── Computador do usuário ─────────────────────────────┐
│                                                                                 │
│  SmartCut.exe (Electron)                                                        │
│   ├── processo principal (electron/main.js, backend.js)                         │
│   │     • abre a janela e serve o React por app://bundle (CSP estrita)          │
│   │     • sobe o backend (smartcut-backend.exe) e espera o /health              │
│   │     • gera PDF dos relatórios (printToPDF), atualização automática          │
│   │                                                                             │
│   ├── janela (React 18 + Vite, frontend/) ──── HTTP localhost:8000/api/v1 ──┐   │
│   │                                                                         │   │
│   └── backend (FastAPI, Python 3.12, empacotado com PyInstaller) ◄──────────┘   │
│         • regras de negócio, motor de encaixe, NF-e, relatórios                 │
│         • SQLite + arquivos na pasta de dados (%APPDATA%\smartcut)              │
└─────────────────────────────────────────────────────────────────────────────────┘
```

- **Electron** (`electron/`): é o aplicativo instalado. Ao abrir, mostra
  `loading.html`, inicia o backend como processo filho, passa a ele por
  variáveis de ambiente os caminhos da pasta de dados e os segredos da
  instalação, e carrega o frontend. Ao fechar, encerra o backend.
- **Frontend** (`frontend/`): React 18 com CSS Modules. Conversa com o backend
  só por HTTP (`/api/v1/...`). Login com JWT (cookie HttpOnly + token guardado
  pelo processo principal, nunca em `localStorage`).
- **Backend** (`backend/`): FastAPI + SQLAlchemy 2. Organização em camadas:
  `routers/` (rotas HTTP, respostas `{data, error}`) → `services/` (regras) →
  `models/` (tabelas). Validação de entrada em `schemas/` (Pydantic).
- **Banco**: SQLite em modo WAL. A estrutura é governada por migrations
  Alembic versionadas (`backend/alembic/versions/`), aplicadas
  automaticamente no boot do backend.

Em desenvolvimento as mesmas partes rodam separadas: `uvicorn` na porta 8000,
Vite na 5173 (com proxy de `/api`), e opcionalmente o Electron apontando para
eles.

### Acesso e permissões

- **Sistema de gestão**: usuários com permissões por módulo e ação (`ver`,
  `criar`, `editar`, `excluir`, e ações fiscais próprias como transmitir e
  cancelar NF-e). Administradores passam em tudo. No primeiro acesso o sistema
  pede a criação do administrador.
- **Painel do vendedor** (`/vendedor`, pensado para celular): login próprio
  do vendedor, metas, pedidos do mês, catálogos e leads.
- Um único segredo JWT por instalação (gerado pelo Electron e guardado com o
  cofre do Windows).

---

## b. Módulos

| Menu | Módulo | O que faz |
|---|---|---|
| CADASTROS | Clientes, Transportadoras | Clientes/fornecedores com dados fiscais (CNPJ/CPF, IE, município IBGE). |
| | Produtos e grades | Produto pai, grade cor × tamanho (tabelas de grade) e SKUs. Cada produto aponta para seus moldes. `dupla_camada` marca produto forrado. |
| | Tecidos | Três níveis: **modelo** (ex.: SUPLEX; `max_camadas`, `tem_direcao`) → **cor** (largura útil, gramatura, encolhimento) → **lote** (peso, valor/kg, estoque). Alerta de estoque crítico. |
| | Moldes | Importa PLT, DXF e ADS; organiza em grupos (referência) e partes por tamanho; sentido do fio; **tipo de corte** obrigatório (ver seção d). |
| PRODUÇÃO | Ordem de Corte | Do pedido até a ficha de corte (seção c). |
| | Encaixe Rápido | Encaixe sem pedido completo: escolhe tecidos e peças e gera na hora. |
| | Encaixes | Lista e visualizador de todas as mesas geradas. |
| VENDAS | Pedidos de venda | Itens por SKU, tabela de preço, condição de pagamento, comissão; impressão pelo relatório relVen001. |
| FISCAL | NF-e, TES | Emissão, transmissão à SEFAZ, cancelamento, carta de correção e DANFE. |
| FINANCEIRO | Painel, Fluxo de caixa, Compras, Vendas, Contas | Contas a pagar/receber, parcelas, anexos (NF/boleto), saldo por conta, projeção, metas, pacote para a contabilidade. |
| GESTÃO | Precificação, Projeção | Preço de venda a partir do custo detalhado (Simples Nacional) e simulação de resultado. |
| Rodapé ⚙ | Configurações | Empresa (logo, dados fiscais), Produção (mesa, tempo limite, tolerância), Gerais, Tabelas de preço, Vendedores, Usuários. |
| `/vendedor` | Painel do vendedor | Metas e bônus, pedidos por mês, catálogos PDF, leads com mapa. |

---

## c. Fluxos principais

### Pedido de venda → Ordem de Corte → Encaixe → Ficha de corte

1. **Pedido de venda**: itens com produto, cor e tamanho (SKU), preços da
   tabela escolhida.
2. **Ordem de Corte (OC)**: criada a partir do pedido (uma OC ativa por
   pedido), num assistente de 3 passos:
   - *Conferência* — itens do pedido e os moldes de cada produto; escolha de
     **Organizar o corte** (por produto ou por cor, seção d).
   - *Tecidos* — o lote de cada produto/cor, o comprimento máximo da mesa e a
     qualidade.
   - *Encaixes* — a geração roda em segundo plano; a tela mostra a fase, a
     mesa atual e a **decisão do sistema** (tipo de enfesto e o porquê). Dá
     para cancelar sem gravar nada.
3. **Encaixes**: cada encaixe gravado é uma **mesa** (uma parte de um enfesto),
   com o desenho das peças, comprimento, consumo e custo.
4. **Ficha de corte** (relatório relPro001): o que o cortador precisa para
   estender e cortar cada mesa, com o desenho visto do lado dele.
5. **Produção e estoque**: a OC passa por RASCUNHO → ENVIADA → EM_CORTE →
   CONCLUIDA. Enviada ou em corte, o peso planejado fica **reservado** nos
   lotes; na conclusão é **baixado**; ao reabrir, **estornado**.

O **Encaixe Rápido** usa o mesmo motor e a mesma decisão de enfesto, sem OC:
cria um pedido mínimo, gera as mesas e abre a mesma ficha de corte
(relPro001 pelo id do pedido do encaixe).

### Pedido → NF-e → Financeiro

1. A NF-e é criada a partir do pedido (dados do cliente, itens, TES com CFOP e
   tributação) e numerada pela série da empresa.
2. **Transmitir** assina o XML com o certificado A1 da empresa e envia à
   SEFAZ; o XML autorizado e o DANFE ficam na pasta de dados
   (`uploads/nfe/...`). Cancelamento e carta de correção seguem o mesmo
   caminho.
3. **Financeiro**: as vendas entram em *Vendas financeiras* (contas a
   receber) — manualmente ou importando os XMLs das notas (importação em
   lote); compras entram do mesmo jeito em *Compras*. Cada venda/compra gera
   os lançamentos das parcelas, que viram entradas/saídas confirmadas ao
   registrar o pagamento numa conta bancária.

---

## d. Produção: motor de encaixe e plano de corte

### Termos

- **Molde / peça**: o contorno de uma parte da roupa num tamanho.
- **Risco**: o desenho das peças sobre o tecido (o "encaixe").
- **Enfesto**: o tecido estendido em várias camadas sobre a mesa; o risco é
  cortado de uma vez em todas as camadas.
- **Mesa**: um enfesto mais comprido que a mesa da fábrica é dividido em
  mesas (partes). Cada mesa vira um encaixe.

### Motor de encaixe (`backend/services/nesting_v2/`)

- **spyrrow** faz o encaixe propriamente dito (strip packing de polígonos
  reais) em cada mesa.
- **OR-Tools CP-SAT** divide as peças de um enfesto entre as mesas, até o
  comprimento máximo, equilibrando a área e mantendo pares juntos.
- As rotações respeitam o sentido do fio do molde. A geração roda como job em
  segundo plano (`services/nesting_jobs.py`); se o motor falhar, tenta mais
  uma vez com outra semente no perfil Rápido e, falhando de novo, não grava
  nada.

### Tipo de corte do molde

Obrigatório em cada parte do molde:

| Tipo | Peças por conjunto | Enfesto simples | Enfesto duplo |
|---|---|---|---|
| `simples` | 1 | 1 peça | 1 peça |
| `par` | 2 (direita e esquerda) | a 2ª sai **espelhada** no desenho | as duas iguais — a alternância das camadas faz direita e esquerda |
| `par_sem_espelho` | 2 iguais | nunca espelhadas | nunca espelhadas |

A tela de moldes avisa (sem bloquear) quando uma peça assimétrica está
marcada como `simples` ou `par_sem_espelho`.

### Enfesto simples ou duplo

O usuário não escolhe; o sistema decide por grupo de corte
(`nesting_v2/decisor.py`) e mostra o motivo:

- **Enfesto simples** (`MESMA_FACE`): todas as camadas com o direito para cima.
- **Enfesto duplo** (`FACE_A_FACE`): vai e volta virando o tecido; mais rápido
  de estender.

O duplo é descartado quando o tecido tem direção (estampa/pelo), há peça única
assimétrica, há `par_sem_espelho` assimétrico, ou só cabe 1 camada. Entre as
formas válidas ganha o **menor consumo**; num empate técnico (< 1%): sem sobra
antes de com sobra, depois **menos mesas**, e por fim as regras da produção —
produto forrado (`produtos.dupla_camada`) → duplo; 2 ou 3 camadas → simples;
senão duplo. Enfesto duplo com peça `par` usa número par de camadas.

### Plano de corte por produto e enfesto multicor

Na OC, **Organizar o corte** (`ordens_corte.organizar_por`):

- **Por produto** (padrão): o plano de corte (`services/planejamento/
  plano_corte.py`, CP-SAT) escolhe quais riscos desenhar e **quantas camadas
  de cada cor** vão em cada risco. Várias cores dividem o mesmo enfesto
  (**enfesto multicor**, ex.: PRETO 7 · MARROM 7). Um risco nunca mistura
  produtos. Regras: nenhuma cor falta; sobra só quando inevitável; soma das
  camadas ≤ `max_camadas` do tecido; cores do mesmo modelo de tecido com até
  5 cm de diferença de largura podem dividir o enfesto; aceita até a
  **tolerância de tecido** (padrão 2%) a mais para ter menos mesas e menos
  desenhos. O motor roda uma vez por risco. O resultado é determinístico.
- **Por cor** (fluxo antigo): tudo o que usa o mesmo lote vai no mesmo risco,
  misturando produtos.

No enfesto multicor cada lote tem sua linha em `encaixe_camadas`, e a
reserva/baixa/estorno de estoque soma por essas linhas.

### Qualidade por orçamento de tempo

A qualidade padrão é **Automática**: cada risco começa no perfil Rápido e sobe
para Equilibrado e Máximo enquanto houver tempo, priorizando os riscos mais
pesados, dentro do **tempo limite da ordem de corte** (Configurações >
Produção, padrão 300 s). O custo de cada risco é estimado antes de encaixar
(`planejamento/custo.py`). Rápido, Equilibrado e Máximo também podem ser
escolhidos à mão no "Avançado".

Se a mesa configurada na OC é menor que a maior mesa da fábrica, a geração
simula a mesa maior e sugere a troca quando a economia passa do percentual de
alerta.

---

## e. Relatórios

Os documentos impressos são **modelos HTML editáveis** (Jinja2 em sandbox) na
pasta `relatorios/`:

| Código | Arquivo | Documento |
|---|---|---|
| relVen001 | `vendas/relVen001.html` | Pedido de venda |
| relPro001 | `producao/relPro001.html`, `relPro001_basico.html` | Ficha de corte (da OC por produto, por cor, ou do Encaixe Rápido) |

- O backend monta os dados (`services/relatorios/dados_*.py`) e renderiza o
  modelo (`GET /api/v1/relatorios/{codigo}/html?id=...`). O modelo só recebe
  dados simples; desenhos (como a mesa da ficha) chegam prontos.
- `config.json` diz qual variante é a padrão; variantes novas
  (`relPro001_<nome>.html`) aparecem para escolha no visualizador.
- O frontend abre o relatório num visualizador sobre a tela; no app instalado
  o Electron gera o PDF (A4, rodapé "Página X/Y") para imprimir ou salvar.
- **Sincronização**: o instalador leva os modelos originais em
  `resources/relatorios-padrao`. A cada abertura, `electron/relatorios-sync.js`
  copia para `%APPDATA%\smartcut\relatorios` o que falta e atualiza o que o
  usuário não editou; um modelo **editado** é mantido e a versão nova é
  gravada ao lado como `<nome>.novo.html`. Nada é apagado.
- Ainda em ReportLab (PDF gerado em código): DANFE da NF-e e o pacote da
  contabilidade.

Padrão visual dos documentos: A4, preto e branco, com o logo da empresa.

---

## f. Pasta de dados do usuário (`%APPDATA%\smartcut`)

Tudo o que é do usuário fica fora da pasta de instalação — reinstalar ou
atualizar o SmartCut não apaga nada disso.

```
%APPDATA%\smartcut\
├── smartcut.db              banco (SQLite) + smartcut.db-wal / -shm
├── backups\                 cópias automáticas do banco (as 30 mais recentes)
├── uploads\                 arquivos enviados: financeiro\ (anexos), logos\,
│                            nfe\ (XMLs e DANFEs), catalogos\, moldes
├── Certificados\            certificado digital A1 (.pfx) da empresa
├── relatorios\              modelos de relatório editáveis (seção e)
├── smartcut-jwt-secret.bin  segredo JWT da instalação (cifrado pelo Windows)
├── smartcut-cert-key.bin    chave que cifra a senha do certificado
├── (token da sessão)        login salvo, cifrado pelo Windows
└── smartcut.log             log do aplicativo (com rotação)
```

- O banco guarda caminhos **relativos** a essa pasta (`uploads/...`); o código
  resolve tudo por `backend/services/pasta_dados.py`.
- A senha do certificado é gravada cifrada (AES-256-GCM, `enc:v1:...`); a
  chave fica só no cofre do Windows. Quem copia só o banco não recupera a
  senha.
- Em desenvolvimento a "pasta de dados" é `backend/` (banco
  `backend/smartcut.db`, arquivos em `backend/uploads/`) e os relatórios são
  lidos de `relatorios/` na raiz do projeto.

---

## g. Instalação, atualização e backup

### Instalação

`SmartCut Setup <versão>.exe` (NSIS, pt-BR): permite escolher a pasta e cria
atalhos. Na primeira execução o app cria a pasta de dados, o banco (já na
estrutura atual, pelas migrations), os segredos da instalação e pede o
cadastro do administrador.

### Atualização

- **Automática** (`electron-updater`): ativa quando a variável
  `SMARTCUT_UPDATE_URL` aponta para o repositório com o `latest.yml` e o
  instalador. O download é feito em segundo plano e a instalação acontece ao
  fechar o app (ou em "Reiniciar agora").
- **Manual**: rodar o instalador novo por cima. Em ambos os casos a pasta de
  dados é preservada e o backend aplica as migrations novas no boot.

### Backup

- O backend copia o banco no boot e a cada 6 h para `backups\` ao lado do
  `.db` (cópia consistente, com checkpoint do WAL), mantendo os **30 mais
  recentes**. Configurável por `BACKUP_DIR`, `BACKUP_MANTER` e
  `BACKUP_INTERVAL_SEC`.
- Para guardar fora do computador, copie a pasta `%APPDATA%\smartcut` inteira
  (banco, uploads, certificados e relatórios) com o SmartCut fechado.
- **Restaurar**: fechar o SmartCut; copiar o backup escolhido
  (`backups\smartcut_<data>_<hora>`) por cima de `smartcut.db`; apagar
  `smartcut.db-wal` e `smartcut.db-shm` se existirem; abrir o SmartCut.

---

## h. Fórmulas e regras críticas

Não alterar sem decisão explícita:

```python
metros = peso_kg * 1000 / (gramatura * largura_cm / 100)     # peso do lote → metros
preco_venda = custo_base / (1 - aliquota - margem)          # Simples Nacional
comissao = total_pedido * tabela.comissao_pct
bonus_logistica = bonus_valor if total_mes >= meta_ativacao else 0
bonus_expansao = floor(novos_clientes / meta_n) * bonus_valor
camadas = min(ceil(qtd / pecas_por_enfesto), max_camadas)
```

O inverso da primeira (metros → peso) é `gramatura_service.metros_para_peso`,
usado no consumo do encaixe. Peso, custo e metros de um encaixe são de **uma
camada**; os totais multiplicam por `num_camadas`.

---

## Próximos passos

O produto principal passa a ser o módulo de Corte, vendido como ponte entre
o pedido e o corte ([ESTRATEGIA.md](ESTRATEGIA.md)). Roadmap (detalhes,
decisões e status em [ARQUITETURA.md](ARQUITETURA.md)):

1. **F0 — Robustez do Corte**: numerações atômicas de OC, encaixe e códigos,
   trava no estoque e nas transições da OC, controle de edição simultânea.
2. **F1 — Corte independente de Vendas**: origem genérica do pedido de
   corte, Encaixe Rápido sem pedido de venda, `ConfiguracaoProducao`
   separada, ficha de corte sem Fiscal/Vendas.
3. **F2 — Consumo previsto x real** por OC e relatório de economia mensal.
4. **F3 — Integração**: importação CSV/XML de pedidos, API
   `/api/integracao/v1`, conectores Bling/Tiny, retorno de consumo.
5. **F4 — Login, segurança e licença por módulo.**
6. **F5 — Diferenciais**: áreas proibidas no encaixe, compra de tecido,
   saída HPGL, pedido por WhatsApp com IA, projetor, digitalização por foto.

Depois: PostgreSQL e modo servidor; ERP (vendas, fiscal, financeiro, Fase 5);
idiomas.

Pendências pontuais:

1. Corrigir o erro 422 em `POST /financeiro/metas`.
2. Moldes: alinhamento do SVG importado, detecção de piques, margem de
   costura, tecido tubular (dobrado), zoom/pan no editor.
3. Pedidos de venda: bugs conhecidos de menu, autocomplete e scroll da grade.
4. Painel do vendedor: finalizar dashboard de metas e pedidos por mês.
5. Financeiro: despesas recorrentes e relatórios por categoria/fornecedor.
6. Redesign: aplicar a cor principal do sistema (a definir; sem azul).

Fora do escopo: versão web, SaaS ou multiempresa. O SmartCut é instalado na
empresa do cliente (servidor e estações na rede local); na nuvem ficam só
licenças e atualizações. O planejamento antigo (fases, deploy web, custos de
SaaS) foi descartado e fica só como registro em
[historico/ROADMAP.md](historico/ROADMAP.md).
