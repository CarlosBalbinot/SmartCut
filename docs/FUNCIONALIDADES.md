# FUNCIONALIDADES.md — O que existe hoje (Junho 2026)

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

**Limitações atuais (a corrigir na Fase 3):**
- Leitura do PLT pode gerar SVG desalinhado (molde aparece rotacionado ou fora do canvas)
- Piques (entalhes de encaixe) nem sempre são detectados corretamente
- Sem suporte a margem de costura automática
- Sem suporte a tecido tubular/dobrado

---

## PRODUÇÃO

### Encaixe Rápido
**Localização**: Menu → PRODUÇÃO → Encaixe Rápido

Permite fazer um encaixe sem criar um pedido completo:
- Seleciona múltiplos tecidos em cascata
- Cor do tecido é aplicada automaticamente na visualização
- Resultado mostra aproveitamento (%)
- Antes de gerar, as peças são validadas: peça mais larga que a largura útil
  do tecido ou geometria de molde inválida impedem a geração, com o nome do
  molde e do tecido na mensagem; peça maior que a mesa só avisa
- Qualidade **Automática** por padrão (o perfil sai do número de peças do
  enfesto) ou RÁPIDO/EQUILIBRADO/MÁXIMO no seletor "Avançado"
- Se o motor falhar, ele tenta de novo automaticamente (outra semente, perfil
  Rápido); na segunda falha nada é gravado e a mensagem diz que os encaixes
  anteriores foram mantidos

---

### Encaixes
**Localização**: Menu → PRODUÇÃO → Encaixes

Encaixes completos vinculados a pedidos ou criados manualmente.
Motor de encaixe atual: **spyrrow + OR-Tools** (spyrrow = strip packing de peças
irregulares; OR-Tools CP-SAT divide o enfesto em mesas), qualidade Automática por
padrão ou RÁPIDO/EQUILIBRADO/MÁXIMO no seletor "Avançado".

A qualidade Automática é resolvida por **orçamento de tempo**, não por contagem
de peças: cada risco começa no perfil Rápido e sobe um degrau (Equilibrado,
Máximo) enquanto sobrar tempo, na fila dos riscos mais pesados, dentro do limite
de Configurações > Produção > "Tempo limite da ordem de corte (s)" (padrão
300 s). O preço de cada risco é estimado antes de qualquer encaixe
(`backend/services/planejamento/custo.py`) e a escolha fica registrada no
`mapa_json` do risco (`qualidade_automatica`). Quando nem o perfil mais barato
cabe no limite, a geração avisa que vai passar do prazo.

O limite vale para a **ordem inteira**: a comparação de enfesto (que roda os
candidatos no perfil Rápido para escolher enfesto simples ou duplo) acontece
antes e sai da mesma conta. Antes ela tinha um relógio à parte (teto fixo de
180 s, `decisor.TEMPO_COMPARACAO_S`) e o gasto não era do limite de ninguém:
na OC-0004 ela consumiu 180 s dos 300 s, gastados deciding um único lote e
deixando os outros dois no padrão — para escolher, no fim, o próprio padrão
seguro. Agora ela ganha **me metade da folga** que sobrar depois do piso do
pedido (o plano mais barato possível, estimado sem rodar o motor). Se o piso
já come o limite inteiro, a comparação não roda e o motivo na tela diz
exatamente isso. Dentro da folga, os candidatos são simulados do mais barato
para o mais caro e só começam se der tempo — então o mesmo segundo decide
mais lotes, e a OC sai igual em execuções diferentes.

Medido na OC-0004 (300 un de legging, 3 lotes, 324 peças, mesa de 150 cm) com
`backend/scripts/medir_oc.py`, no banco de cópia. As duas últimas colunas são
faixas de três rodadas:

| | perfil antigo (por contagem de peças) | só o orçamento de qualidade | + comparação orçada |
|---|---|---|---|
| Tempo | 2.008 s | 358,7 s | **278 a 281 s** |
| Tecido | 42,88 m | 43,29 m | 42,76 a 43,24 m |
| Mesas | 37 | 37 | 37 |
| Perfis dos 8 riscos | 8 Máximo | 8 Rápido | 8 Rápido |

7,2× mais rápido que o perfil antigo, com o mesmo tecido (dentro da tolerância
de 2%) e as mesmas 37 mesas. A comparação orçada rende 80 s sobre os 358,7 s
— e não os 180 s que ela consumia, porque parte daqueles 180 s não era
desperdício: a geração reaproveita do cache o que a comparação já rodou no
perfil Rápido. O que se economiza é a refação. O que muda de verdade é o
resultado: **~279 s cabe nos 300 s que o usuário cadastrou; 358,7 s não
cabia.**

O que ficou determinístico é a **decisão**: com o piso ocupando o limite
inteiro, os três lotes vão para o padrão seguro sempre, pelo mesmo motivo, sem
depender de qual lote o relógio deixasse decidir primeiro. Nas três rodadas
saíram sempre as mesmas 37 mesas e os 8 riscos no Rápido. O **desenho** ainda
oscila um pouco (0,5% de tecido entre rodadas) porque o motor tem teto de tempo
por enfesto (`QUALIDADES["RAPIDO"]["tempo_max_s"]`) e o empacotamento final
depende de quanto tempo a máquina deu — isso é do motor, não da decisão, e é
anterior a este trabalho.

O aviso de "vai passar do prazo" aparece mesmo nesta OC, porque o estimador é
deliberadamente pessimista (306 s estimados para 279 s medidos: ele erra para o
lado caro para não estourar o prazo). O texto avisa que a estimativa é o teto,
não a média.

### Enfesto simples ou duplo: o que decide o empate

Quando as duas formas de enfesto empatam no consumo de tecido (diferença menor
que 1%), a preferência é destas regras, na ordem:

1. **Produto de dupla camada** — produto **forrado**. Vem do cadastro
   (`produtos.dupla_camada`, aba Dados do cadastro de produtos, rótulo
   "Produto de dupla camada (forrado)"). A produção quer as duas camadas
   cortadas de uma vez, então o empate vai para o enfesto duplo. Vence mesmo
   com poucas camadas.
2. **2 ou 3 camadas** — o empate vai para o enfesto simples.
3. **Caso contrário** — enfesto duplo, porque é mais rápido de estender.

Fora do empate ganha sempre o **menor consumo de tecido**, e o enfesto duplo é
descartado por completo quando o tecido tem direção (estampa/pelo) ou quando há
peça única assimétrica (sairia espelhada em metade das camadas).

"Dupla camada" é **cadastro, nunca inferência**. A regra anterior deduzia
"produto dupla" de ter peças em par (ou de as quantidades darem camadas pares) e
estava errada: quase toda legging tem par (costas direita e esquerda) e isso não a
torna forrada. Na OC-0002 a MAXXI VERDE MILITAR era LEGGING FLARE — peça em par,
não forrada — e por isso saía em enfesto duplo; com o cadastro corrigido ela sai
em enfesto simples, pela regra das 2 camadas.

O que continua vindo do "par" é só **geometria**, e está certo: peça em par nunca
é tratada como peça única assimétrica (ela vem com a cópia espelhada), e no
enfesto duplo o número de camadas é arredondado para par, porque as camadas se
alternam de lado e a peça precisa sair com um de cada.

**Histórico:**
- Node.js skyline packer (~58% de aproveitamento típico) — removido em 2026-09-29.
- Deepnest C++ — compilado para Mac, não roda no Windows. Requer recompilação via Docker/WSL.

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
- **PDF Formulário de Corte**: layout específico para produção

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
