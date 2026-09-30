# FUNCIONALIDADES.md — O que existe hoje (Setembro 2026)

Este arquivo descreve tudo que está implementado e funcionando no SmartCut.

---

## CADASTROS

### Tecidos
**Localização**: Menu → CADASTROS → Tecidos

Hierarquia de três níveis:
- **Modelo** → ex: "Suplex 4 Vias"
- **Cor** → vinculada ao Modelo, com código hex para visualização
- **Lote** → vinculado à Cor, contém: peso (kg), largura (cm), gramatura (g/m²), fornecedor, data de entrada

**Funcionalidades:**
- CRUD completo nos três níveis
- Alerta visual quando peso do lote ≤ 5kg (estoque crítico)
- Histórico de lotes por cor
- Cálculo automático de metros a partir do peso: `metros = peso_kg * 1000 / (gramatura * largura_cm / 100)`
- No **modelo**: máximo de camadas por enfesto (`max_camadas`, o teto do plano
  de corte) e **tecido com direção** (estampa ou pelo: o enfesto é sempre
  simples)

---

### Moldes
**Localização**: Menu → CADASTROS → Moldes

**Funcionalidades:**
- Importação de arquivos PLT, DXF e ADS
- Preview em SVG após importação
- Organização por **Grupos de Molde** (cada grupo tem um código de referência de venda)
- Graduação automática de tamanhos P, M, G, GG
- **Sentido do fio**: linha arrastável com ângulo livre (salvo em graus)
- **Flip horizontal e vertical** do molde
- Código de referência por grupo para identificação no pedido
- **Tipo de corte obrigatório** em cada parte (importação e edição), sem valor
  de fábrica: **Simples** (1 peça), **Par** (2 peças espelhadas — uma de cada
  lado) ou **Par sem espelho** (2 peças iguais). Decide quantas peças saem de um
  molde e se a segunda é espelhada.
- **Aviso de simetria** (não bloqueia): peça assimétrica marcada como Simples
  ou Par sem espelho mostra "Esta peça não é simétrica. Se a roupa tem uma de
  cada lado (direita e esquerda), o tipo correto é Par." — mesma medida do
  decisor do enfesto (`POST /api/v1/moldes/simetria`)

**Limitações atuais (a corrigir na Fase 3):**
- Leitura do PLT pode gerar SVG desalinhado (molde aparece rotacionado ou fora do canvas)
- Piques (entalhes de encaixe) nem sempre são detectados corretamente
- Sem suporte a margem de costura automática
- Sem suporte a tecido tubular/dobrado

---

## PRODUÇÃO

### Motor de encaixe (v2)

Um motor só, embutido no backend Python (`backend/services/nesting_v2/`):

- **spyrrow** (MIT) — strip packing de peças irregulares com o polígono real
  do molde; é o motor de cada mesa.
- **OR-Tools CP-SAT** (Apache-2.0) — divide o enfesto em mesas de comprimento
  até o limite, equilibrando área e respeitando pares.

O motor v1 (Node.js, skyline por bounding box, ~58% de aproveitamento) foi
removido: não há mais seletor de motor nem motor reserva. Sem spyrrow/ortools
(executável montado errado) a geração avisa que é preciso reinstalar. No boot o
log diz `Motor v2 disponível (spyrrow …, ortools …)`.

Regras do desenho:
- rotações pelo sentido do fio; `par` entra duas vezes — no enfesto simples a
  2ª cópia sai **espelhada**, no enfesto duplo as duas saem iguais (a
  alternância das camadas faz direita e esquerda);
- `par_sem_espelho`: duas peças **iguais**, nunca espelhadas, em qualquer
  enfesto;
- a tabela de cada mesa é **por molde**; a grade por tamanho fica no resumo do
  enfesto.

A geração roda **em segundo plano** (`services/nesting_jobs.py`): a tela mostra
a fase e a mesa atual, e dá para cancelar sem gravar nada. Falha do motor →
uma nova tentativa automática (outra semente, perfil Rápido); na segunda falha
nada é gravado.

### Qualidade: orçamento de tempo

Qualidade **Automática** por padrão, ou RÁPIDO / EQUILIBRADO / MÁXIMO no
"Avançado". A Automática é resolvida por **orçamento de tempo**
(`backend/services/planejamento/custo.py`), não por contagem de peças: cada
risco começa no perfil Rápido e sobe um degrau (Equilibrado, Máximo) enquanto
sobrar tempo, na fila dos riscos mais pesados, dentro de Configurações >
Produção > "Tempo limite da ordem de corte (s)" (padrão 300 s). O preço de cada
risco é estimado antes de qualquer encaixe e a escolha fica no `mapa_json` do
risco (`qualidade_automatica`). Quando nem o perfil mais barato cabe no limite,
a geração avisa que vai passar do prazo (a estimativa é o teto, não a média).

O limite vale para a **ordem inteira**. Na OC organizada por COR, a comparação
de enfesto (que roda os candidatos no perfil Rápido) sai da mesma conta: ganha
metade da folga que sobrar depois do piso do pedido; se o piso já come o
limite, ela não roda e os lotes vão para o padrão seguro, com o motivo na tela.
Na OC por PRODUTO a decisão é pela estimativa do plano e não gasta tempo de
motor.

Medido na OC-0004 (300 un de legging, 3 lotes, mesa de 150 cm), banco de cópia,
com `backend/scripts/medir_oc.py`:

| | perfil antigo (por contagem de peças) | só o orçamento de qualidade | + comparação orçada |
|---|---|---|---|
| Tempo | 2.008 s | 358,7 s | **278 a 281 s** |
| Tecido | 42,88 m | 43,29 m | 42,76 a 43,24 m |
| Mesas | 37 | 37 | 37 |

### Enfesto simples ou duplo (decisão automática)

O usuário não escolhe como estender: para cada grupo de corte o sistema avalia
as formas válidas e explica o porquê no quadro "Decisão do sistema"
(`services/nesting_v2/decisor.py`). Na tela e na ficha os nomes são os da
produção — **enfesto simples** (MESMA_FACE, todas as camadas com o direito para
cima) e **enfesto duplo** (FACE_A_FACE, vai e volta virando o tecido).

O enfesto duplo é descartado quando: o tecido tem direção (estampa/pelo,
`modelos_tecido.tem_direcao`); há peça única assimétrica; há `par_sem_espelho`
assimétrico; o grupo tem 1 camada; ou o tecido aceita no máximo 1 camada. O
motivo lista **todas** as razões e todas as peças envolvidas, e a `regra`
gravada traz os códigos delas (ex.: `PAR_SEM_ESPELHO_ASSIMETRICO+UMA_CAMADA`).

Critério:
1. menor consumo de tecido;
2. empate técnico (diferença < 1%): sem sobra antes de com sobra; depois
   **menos mesas**; só entre os que empatam também em mesas valem as regras da
   produção — produto de **dupla camada** (forrado, `produtos.dupla_camada`)
   → enfesto duplo; 2 ou 3 camadas → enfesto simples; senão enfesto duplo
   (mais rápido de estender).

"Dupla camada" é cadastro, nunca inferência: peça em par (costas direita e
esquerda) existe em quase toda legging e não a torna forrada. Enfesto duplo com
peça `par` usa camadas pares.

### Encaixe Rápido
**Localização**: Menu → PRODUÇÃO → Encaixe Rápido

Encaixe sem criar pedido completo: tecidos em cascata, cor do tecido na
visualização, aproveitamento (%). Antes de gerar, as peças são validadas (peça
mais larga que a largura útil ou geometria inválida bloqueiam, com o molde e o
tecido na mensagem; peça maior que a mesa só avisa). Usa o mesmo motor, a
decisão de enfesto e a qualidade da Ordem de Corte (agrupamento por lote).

### Encaixes
**Localização**: Menu → PRODUÇÃO → Encaixes

Encaixes vinculados a pedidos/OCs ou criados no Encaixe Rápido. Cada encaixe
é uma **mesa** (parte do enfesto), com número próprio (ENC-001…).

### Ordem de Corte
**Localização**: Pedido de venda → Ordem de Corte (uma OC ativa por pedido)

Assistente em 3 passos — **Conferência** (itens do pedido, moldes resolvidos
pelo SKU e o seletor "Organizar o corte"), **Tecidos** (lote de cada
produto/cor, comprimento máximo, qualidade e o "Avançado") e **Encaixes**
(geração em segundo plano, decisão do sistema, sugestão de mesa maior).

**Organizar o corte** (`ordens_corte.organizar_por`):
- **Por produto** (padrão das OCs novas) — o **plano de corte por produto**
  (`services/planejamento/plano_corte.py`, CP-SAT): quais riscos desenhar e
  quantas camadas de **cada cor** vão em cada risco. Várias cores dividem o
  mesmo enfesto (**enfesto multicor**, ex.: PRETO 7 · MARROM 7). Um risco nunca
  mistura produtos.
- **Por cor** — o comportamento de antes: tudo o que usa o mesmo lote entra no
  mesmo risco, misturando produtos. As OCs anteriores a esta opção ficaram em COR.

Plano de corte por produto:
- riscos candidatos pelos divisores da grade de cada cor (mais os riscos do
  plano por cor, para que ele seja sempre possível); até 12 mesas por risco;
- nenhuma cor falta; **sobra só quando inevitável** (no enfesto simples, zero;
  no duplo com par, a que as camadas pares obrigam) — nunca peça a mais para
  economizar desenho;
- teto: a soma das camadas de todas as cores de um enfesto ≤ `max_camadas` do
  modelo de tecido; enfesto duplo com `par` → camadas pares por cor;
- empilham-se cores do **mesmo modelo de tecido** com diferença de largura de
  até **5 cm**; cada risco é desenhado numa das larguras do grupo e só recebe
  cores de largura maior ou igual — o comprimento a mais na largura menor entra
  no consumo;
- critério: menor consumo; aceitando até a **tolerância de tecido** (padrão
  2%, Configurações > Produção) a mais, **menos mesas**, depois **menos
  desenhos**;
- comprimento e mesas estimados sem motor (`planejamento/estimador.py`:
  área / (largura × 0,85) + 10 cm de ponta por mesa, ocupação média de 78% da
  mesa — ajustado aos riscos reais da OC-0004); o motor roda **uma vez por
  risco** (cache por proporção + largura) e dá o número real;
- determinístico: o mesmo pedido dá o mesmo plano em qualquer máquina.

Medido na cópia do banco (antes = COR, depois = PRODUTO):

| | OC-0004 COR | OC-0004 PRODUTO | Dany COR | Dany PRODUTO |
|---|---|---|---|---|
| Mesas | 37 | 27 | 74 | 19 |
| Desenhos | 8 | 7 | 9 | 19 |
| Metros | 353,58 | 355,06 | 81,30 | 84,17 |
| Tempo | 273 s | 241 s | 578 s | 175 s |

**Estoque por lote**: o peso planejado é **reservado** enquanto a OC está
ENVIADA ou EM_CORTE, **baixado** na conclusão e **estornado** ao reabrir. No
enfesto multicor cada lote é somado pelas linhas de `encaixe_camadas` (peso,
custo e metros de uma camada calculados com o tecido daquele lote — gramatura,
largura, encolhimento e preço); encaixe de um lote só continua pelo
`lote_id`.

**Sugestão de mesa maior**: se o limite da OC é menor que a maior mesa da
fábrica, a geração simula a mesa maior e sugere quando a economia passa de
"Alertar economia a partir de (%)".

### Ficha de corte (relPro001)

Relatórios HTML/Jinja em `relatorios/producao/`, abertos por
`GET /api/v1/relatorios/relPro001/html?id=<oc>` (A4 retrato, P&B, logo):

- `relPro001.html` — formulário de corte; `relPro001_basico.html` — só o
  essencial para estender e cortar. O padrão fica em `relatorios/config.json`.
- **OC por produto**: uma seção por produto → tecido, com a grade do pedido
  (cor × tamanho) e as mesas na ordem de corte: "Mesa 1 · 120 cm · Enfesto
  simples · Camadas: PRETO 7 · MARROM 7", os tamanhos no desenho e o desenho.
  Enfestos do mesmo risco saem num bloco só ("Mesas 1, 2 · mesmo desenho").
- **OC por cor**: a lista de mesas de sempre (dados da mesa e tabela de
  moldes).
- Desenho deitado, visto do cortador: largura na horizontal, "INÍCIO DA MESA"
  embaixo, escala fixa (150 cm ≈ 100 mm), peças espelhadas tracejadas.

---

## VENDAS

### Pedidos de Venda
**Localização**: Menu → VENDAS → Pedidos de Venda

**Funcionalidades:**
- Tabela de preço única por pedido
- Itens com: referência + tecido + tamanhos P/M/G/GG + Plus Size G1/G2/G3
- Plus Size ativado automaticamente quando necessário
- Preço automático baseado em tabela + condição de pagamento
- Cálculo automático de comissão por vendedor
- **PDF Formulário de Pedido**: layout Vaidosa Fitness com logo, A4 P&B
- **Formulário de Corte**: sai da Ordem de Corte do pedido (relPro001, ver PRODUÇÃO > Ficha de corte)

**Bugs conhecidos:**
- Três pontos de menu sumindo em alguns casos
- Autocomplete de cliente/referência às vezes escondido atrás de outros elementos
- Cores de tecido invisíveis em determinadas situações
- Preço automático não carregando em alguns fluxos
- Scroll horizontal da tabela de tamanhos com comportamento irregular

---

## GESTÃO

### Precificação
**Localização**: Menu → GESTÃO → Precificação

Calcula preço de venda com base em custo detalhado:

**Campos de custo:**
- Custo de tecido (por peça)
- Custo de costura
- Custo de linha (overlock + reta)
- Custo de saquinho
- Custo de caixa/embalagem
- Custo de gasolina/frete

**Fórmula Simples Nacional:**
```
preco_venda = custo_base / (1 - aliquota - margem)
```

- Export de resultados em CSV
- Alíquota e margem configuráveis nas Configurações Gerais

---

### Projeção
**Localização**: Menu → GESTÃO → Projeção

Simulação de lucratividade com gráficos Recharts.
Permite simular cenários de produção e ver impacto no resultado.

---

## CONFIGURAÇÕES

**Localização**: Rodapé do menu → ⚙ Configurações (painel unificado)

Dividido em seções:

### Dados da Empresa
- Logo, CNPJ, nome, telefone, email, endereço
- Logo usada nos PDFs

### Produção
- Comprimento máximo da mesa (cm) — a maior mesa da fábrica (sugestão de mesa maior)
- Alertar economia a partir de (%)
- Tempo limite da ordem de corte (s) — orçamento da qualidade Automática
- Tolerância de tecido para simplificar o corte (%) — plano de corte por produto

### Configurações Gerais
- Alíquota Simples Nacional (%)
- Margem de lucro padrão (%)
- Insumos padrão
- Logística
- **Reserva mínima de caixa** (usado no semáforo do financeiro)

### Tabelas de Preço
- CRUD de tabelas
- Produtos com preço à vista e a prazo por referência
- Percentual de comissão por tabela

### Vendedores
- Cadastro completo: nome, CPF, telefone, email
- Credenciais JWT para acesso ao Painel do Vendedor
- Metas personalizadas (valor meta, bônus, meta de ativação, bônus por novos clientes)
- Associação a catálogos

---

## PAINEL DO VENDEDOR

**Rota**: `/vendedor` (mobile first, JWT obrigatório)

**Funcionalidades:**
- Login com logo da empresa
- Dashboard de metas motivador
- Pedidos agrupados por mês em accordion
- Catálogos PDF para download e compartilhamento via WhatsApp
- Leads com integração Google Maps e status de visita

**Status**: Em desenvolvimento — dashboard motivador e pedidos por mês aguardando finalização.

---

## FINANCEIRO (implementado em Junho 2026)

**Localização**: Menu → FINANCEIRO

### Painel
- Cards de saldo por conta bancária
- Cards de resumo: A Pagar / A Receber / Já Pago / Já Recebido / Projeção Final
- Alertas de vencimento (atrasados e próximos 7 dias)
- Gráfico Receita × Despesa × Lucro (últimos 5 meses)
- Projeção em cascata dos próximos 3 meses com semáforo de retirada
- Meta mensal com barra de progresso

### Fluxo de Caixa
- Navegação por mês
- Contas a Pagar com cores por status (verde/amarelo/vermelho)
- Contas a Receber com mesma lógica
- Confirmação de pagamento com seleção de conta bancária
- Visualização de anexos (NF + boletos) por lançamento

### Compras
- Cadastro de compra com fornecedor, valor, parcelas, 1º vencimento
- Geração automática de lançamentos mensais
- Upload de NF (PDF) vinculado a todas as parcelas
- Upload de boleto individual por parcela
- Edição e exclusão de compras
- Expansão para ver parcelas individuais com status

### Vendas Financeiras
- Mesma lógica de Compras, mas para contas a receber

### Contas Bancárias
- PagBank, Banrisul PJ, Banrisul PF, Sicredi, Dinheiro, Cheque
- Saldo calculado em tempo real: saldo_inicial + entradas confirmadas - saídas confirmadas
