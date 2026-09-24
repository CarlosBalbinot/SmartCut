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

---

### Encaixes
**Localização**: Menu → PRODUÇÃO → Encaixes

Encaixes completos vinculados a pedidos ou criados manualmente.
Motor de nesting atual: **Node.js skyline packer** (~58% de aproveitamento típico).

**Planejado mas não implementado:**
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
