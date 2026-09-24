# FINANCEIRO.md — Especificação do Módulo Financeiro

## Visão geral

O módulo Financeiro substitui o controle por Google Planilhas (Google Sheets)
que era recriado manualmente todo mês. O sistema centraliza:

- Contas a Pagar (compras parceladas com boletos anexados)
- Contas a Receber (vendas parceladas com NF e boletos)
- Saldo em tempo real por conta bancária
- Projeção de caixa em cascata (mês a mês)
- Metas mensais de faturamento
- Alertas de vencimento

---

## Contas bancárias da Vaidosa Fitness

| Conta | Tipo |
|---|---|
| PagBank | BANCO |
| Banrisul PJ | BANCO |
| Banrisul PF | BANCO |
| Sicredi | BANCO |
| Dinheiro | DINHEIRO |
| Cheque | CHEQUE |

---

## Fluxo de uma Compra

1. Usuário clica "+ Nova Compra"
2. Preenche: fornecedor, descrição, valor total, nº parcelas, 1º vencimento
3. Faz upload da Nota Fiscal (1 PDF)
4. Faz upload dos boletos (1 PDF por parcela)
5. Sistema cria:
   - 1 registro em `compras_financeiras`
   - N registros em `lancamentos` (tipo PAGAR), um por parcela
   - NF anexada em todas as parcelas (`anexos_lancamento` com tipo=NF)
   - Cada boleto anexado na parcela correspondente (tipo=BOLETO)
6. No Fluxo de Caixa: cada parcela aparece no mês correto
7. Ao clicar na parcela: modal mostra NF + boleto daquela parcela para download

---

## Fluxo de Confirmação de Pagamento

1. Usuário vê parcela com status PENDENTE no Fluxo de Caixa
2. Clica no botão de confirmar
3. Modal: seleciona conta bancária de onde saiu + data do pagamento
4. Sistema:
   - Atualiza `lancamentos.status` para PAGO
   - Salva `lancamentos.conta_bancaria_id` e `lancamentos.data_pagamento`
   - Recalcula saldo da conta: `saldo_inicial - total_pago_confirmado`
5. Cards de saldo no topo atualizam automaticamente

---

## Projeção em cascata

O sistema de projeção funciona em cadeia — o saldo final de um mês
é o saldo inicial do próximo:

```
Junho 2026:
  Saldo inicial (fechamento de Maio):  R$ 17.559,89
  + A receber (lançamentos RECEBER):   R$ 33.378,25
  - A pagar (lançamentos PAGAR):       R$ 24.264,46
  = Saldo projetado:                   R$ 26.673,68
                    ↓ (vira saldo inicial de Julho)

Julho 2026:
  Saldo inicial:   R$ 26.673,68
  + A receber:     R$  5.000,00  ← parcelas futuras já cadastradas
  - A pagar:       R$ 20.000,00  ← parcelas futuras já cadastradas
  = Saldo projetado: R$ 11.673,68

  Semáforo: 🟡 (entre 1x e 2x a reserva mínima)
  Retirada sugerida: R$ 6.673,68 (mantendo R$ 5.000 de reserva)
```

### Semáforo de retirada

| Cor | Condição | Significado |
|---|---|---|
| 🟢 Verde | saldo_projetado > reserva_minima × 2 | Pode retirar com tranquilidade |
| 🟡 Amarelo | reserva_minima < saldo < reserva_minima × 2 | Retirar com cautela |
| 🔴 Vermelho | saldo_projetado < reserva_minima | Não retirar |

Reserva mínima configurada em: Configurações Gerais → `reserva_minima_caixa`
Default: R$ 5.000,00

---

## Status dos lançamentos

| Status | Condição |
|---|---|
| PENDENTE | data_vencimento futura, não pago |
| ATRASADO | data_vencimento passada, não pago (calculado automaticamente) |
| PAGO | confirmado pelo usuário |

A cor da linha na tabela é determinada pelo status:
- PAGO → verde claro
- ATRASADO → vermelho claro
- PENDENTE (vence hoje ou amanhã) → amarelo claro
- PENDENTE normal → branco

---

## Despesas recorrentes (planejado)

Despesas que se repetem todo mês (ex: Costureira Deni, Costureira Aline,
LabelTag, Escritório, NuvemShop, Instagram):

1. Usuário marca uma despesa como "recorrente" ao criar
2. No início de cada mês: sistema pergunta "Deseja gerar as despesas fixas de Julho?"
3. Ao confirmar: gera automaticamente os lançamentos recorrentes do mês
4. Usuário ajusta valores se necessário antes de confirmar

---

## Relatórios planejados

- **Fluxo de caixa mensal PDF**: equivalente à aba do Google Sheets, mas gerado automaticamente
- **Resumo anual**: receitas × despesas × lucro por mês em gráfico
- **Extrato por conta**: todas as movimentações de uma conta bancária
- **Relatório de fornecedor**: total pago para cada fornecedor no período

---

## Integração com outros módulos

### Pedidos de Venda → Vendas Financeiras
Quando um pedido de venda é criado e confirmado, é possível gerar
automaticamente um lançamento em Vendas Financeiras com os dados do pedido.
(Planejado para Fase 2 final)

### Configurações → Reserva mínima
O campo `reserva_minima_caixa` em Configurações Gerais alimenta o semáforo
de retirada na projeção em cascata.
