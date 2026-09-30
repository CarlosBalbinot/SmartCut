# ESTRUTURA.md — Arquitetura e Stack Técnica

## Stack tecnológica

| Camada | Tecnologia | Versão |
|---|---|---|
| Frontend | React + Vite + CSS Modules | React 18 |
| Backend | Python + FastAPI | Python 3.12 |
| Banco de dados | PostgreSQL | 15+ |
| ORM | SQLAlchemy + Alembic | 2.x |
| PDFs | ReportLab; relatórios HTML/Jinja2 (`relatorios/`, impressos em PDF pelo navegador) | — |
| Gráficos | Recharts | — |
| Autenticação | JWT | Painel vendedor |
| Encaixe | Python: spyrrow (strip packing) + OR-Tools CP-SAT (encaixe e plano de corte) | 2.x / 9.x |
| Desktop | Electron | Fase 3 |

---

## Configurações de banco de dados

```
Host:     localhost
Porta:    8844
Usuário:  postgres
Senha:    root
Database: smartcut
```

---

## Estrutura de pastas

```
SmartCut/
├── backend/
│   ├── main.py                  # Entrada FastAPI, registro de routers
│   ├── database.py              # Conexão PostgreSQL, SessionLocal
│   ├── models.py                # Todos os models SQLAlchemy
│   ├── schemas.py               # Schemas Pydantic (request/response)
│   ├── routers/
│   │   ├── tecidos.py
│   │   ├── moldes.py
│   │   ├── pedidos.py
│   │   ├── precificacao.py
│   │   ├── configuracoes.py
│   │   ├── vendedores.py
│   │   └── financeiro.py
│   ├── services/
│   │   ├── nesting_service.py   # geração de encaixes: agrupa, decide o enfesto, roda o motor, grava
│   │   ├── nesting_jobs.py      # geração em segundo plano (progresso, cancelamento)
│   │   ├── ordem_corte_service.py # Ordem de Corte: snapshot, tecidos, estoque (reserva/baixa/estorno)
│   │   ├── plano_enfesto.py     # camadas por tamanho de UM lote (OC por COR)
│   │   ├── planejamento/        # decisões antes do motor (puro, sem banco)
│   │   │   ├── custo.py         # orçamento de tempo da qualidade Automática
│   │   │   ├── plano_corte.py   # plano de corte por produto, enfesto multicor (CP-SAT)
│   │   │   └── estimador.py     # comprimento/mesas de um risco pela área
│   │   ├── nesting_v2/          # motor de encaixe v2 (spyrrow + OR-Tools)
│   │   │   ├── geometria.py     # molde → unidades de corte (fio, pares, espelho)
│   │   │   ├── encaixador.py    # spyrrow (uma mesa)
│   │   │   ├── planejador.py    # CP-SAT: peças por mesa
│   │   │   ├── motor.py         # gerar(): risco → mesas
│   │   │   └── decisor.py       # enfesto simples × duplo (regras e motivo)
│   │   └── relatorios/          # engine dos relatórios HTML + dados (dados_ordem_corte.py)
│   ├── scripts/medir_oc.py      # mede uma OC num banco de CÓPIA (diagnóstico)
│   ├── smartcut.spec            # PyInstaller (npm run build-backend → electron/bin)
│   ├── uploads/
│   │   ├── logos/
│   │   ├── moldes/              # Arquivos PLT/DXF/ADS originais
│   │   └── financeiro/          # PDFs de NF e boletos por lançamento
│   └── alembic/
│       ├── env.py
│       └── versions/
│
├── frontend/
│   ├── src/
│   │   ├── main.jsx             # Entrada React
│   │   ├── App.jsx              # Rotas principais
│   │   ├── components/
│   │   │   ├── Sidebar.jsx      # Menu lateral
│   │   │   └── ...
│   │   ├── pages/
│   │   │   ├── Tecidos.jsx
│   │   │   ├── Moldes.jsx
│   │   │   ├── EncaixeRapido.jsx
│   │   │   ├── Encaixes.jsx
│   │   │   ├── PedidosVenda.jsx
│   │   │   ├── Precificacao.jsx
│   │   │   ├── Projecao.jsx
│   │   │   ├── Configuracoes.jsx
│   │   │   └── financeiro/
│   │   │       ├── PainelFinanceiro.jsx
│   │   │       ├── FluxoCaixa.jsx
│   │   │       ├── ComprasFinanceiro.jsx
│   │   │       └── VendasFinanceiro.jsx
│   │   ├── api/
│   │   │   ├── tecidos.js
│   │   │   ├── moldes.js
│   │   │   ├── pedidos.js
│   │   │   └── financeiro.js
│   │   └── styles/
│   │       └── global.css       # Variáveis CSS globais (sem azul, neutros quentes)
│   ├── public/
│   └── vite.config.js
│
├── relatorios/                  # modelos HTML/Jinja2 dos relatórios (lidos a cada impressão)
│   ├── config.json              # modelo padrão de cada relatório
│   ├── _comum/                  # cabeçalho da empresa
│   ├── vendas/                  # relVen001 (pedido)
│   └── producao/                # relPro001 (ficha de corte) e relPro001_basico
│
├── docs/                        # Esta pasta — documentação completa
│   ├── README.md
│   ├── ESTRUTURA.md
│   ├── FUNCIONALIDADES.md
│   ├── ROADMAP.md
│   ├── ELECTRON.md
│   ├── MOLDES.md
│   └── FINANCEIRO.md
│
├── CLAUDE.md                    # Contexto persistente para Claude Code
├── ROADMAP.md                   # Cópia na raiz para acesso rápido
├── .claudeignore                # node_modules/, uploads/
└── .gitignore
```

---

## Tabelas do banco de dados

### Módulo Tecidos
```
modelos_tecido     → id, nome, created_at
cores_tecido       → id, modelo_id (FK), nome, hex_cor
lotes_tecido       → id, cor_id (FK), peso_kg, largura_cm, gramatura,
                     fornecedor, data_entrada, observacoes
                     ALERTA: peso_kg ≤ 5kg
```

### Módulo Moldes
```
grupos_molde       → id, nome, codigo (referência de venda), descricao
moldes             → id, grupo_id (FK), nome, tamanho, arquivo_original_path,
                     svg_path, area_cm2, perimetro_cm,
                     sentido_fio_graus (float), flip_horizontal (bool),
                     flip_vertical (bool), created_at
```

### Módulo Pedidos
```
pedidos_venda      → id, numero, data, cliente, vendedor_id (FK),
                     tabela_preco_id (FK), condicao_pagamento,
                     total, comissao, status, observacoes
itens_pedido       → id, pedido_id (FK), referencia, tecido_descricao,
                     tamanho_p, tamanho_m, tamanho_g, tamanho_gg,
                     tamanho_g1, tamanho_g2, tamanho_g3,
                     preco_unitario, subtotal
```

### Módulo Encaixes / Ordem de Corte
```
encaixes           → id, numero (ENC-001), pedido_id, ordem_corte_id, lote_id,
                     mapa_json (mesa: placements, grade, decisão, qualidade…),
                     comp_metros, peso_kg, custo_total (de UMA camada),
                     desperdicio_pct, num_camadas, status, descricao
                     Uma linha = uma MESA de um enfesto.
encaixe_camadas    → id, encaixe_id (FK, cascade), lote_id (FK), ordem, cor,
                     camadas, comp_metros, peso_kg, custo (de UMA camada do lote)
                     Só em enfesto multicor (OC por produto); o estoque de cada
                     lote soma estas linhas. Sem linhas = um lote só (lote_id).
ordens_corte       → id, numero (OC-0001), pedido_id (1 ativa por pedido), status
                     (RASCUNHO/ENVIADA/EM_CORTE/CONCLUIDA/CANCELADA),
                     organizar_por (PRODUTO/COR), modo_camadas, tipo_enfesto,
                     decisao_enfesto (JSON), enfesto_avancado (JSON),
                     comprimento_max_cm, qualidade (AUTOMATICO/RAPIDO/
                     EQUILIBRADO/MAXIMO), sugestao_mesa (JSON), pedido_hash,
                     enviada_em, iniciada_em, concluida_em, cortador
itens_ordem_corte  → snapshot dos itens do pedido (produto, SKU, cor, tamanho, qtd)
ordem_corte_tecidos→ lote escolhido para cada (produto, cor)
consumos_lote      → CONSUMO/ESTORNO de peso por lote e OC (conclusão/reabertura)
```

Campos de produção em outras tabelas: `modelos_tecido.max_camadas`,
`modelos_tecido.tem_direcao`, `moldes.tipo_corte` (simples/par/par_sem_espelho,
obrigatório na API), `produtos.dupla_camada`, e em `configuracao_empresa`:
`comprimento_max_mesa_cm`, `alerta_economia_pct`, `tempo_maximo_oc_s`,
`tolerancia_tecido_pct`.

### Módulo Precificação
```
precificacoes      → id, referencia, custo_tecido, custo_costura,
                     custo_linha, custo_overlock, custo_saquinho,
                     custo_caixa, custo_gasolina, custo_base,
                     aliquota, margem, preco_venda, created_at
```

### Módulo Configurações
```
configuracao_empresa     → id, nome, cnpj, logo_path, telefone, email,
                           endereco, cidade, estado
configuracao_custos_fixos → id, aliquota_simples (%), margem_padrao (%),
                            reserva_minima_caixa
tabelas_preco            → id, nome, descricao, comissao_pct, ativo
precos_referencia        → id, tabela_id (FK), referencia, descricao,
                           preco_avista, preco_prazo
```

### Módulo Vendedores
```
vendedores         → id, nome, cpf, telefone, email, ativo
usuarios           → id, vendedor_id (FK), username, password_hash, ativo
catalogos          → id, nome, arquivo_path, created_at
catalogo_vendedor  → id, catalogo_id (FK), vendedor_id (FK)
leads              → id, vendedor_id (FK), nome, telefone, endereco,
                     latitude, longitude, status_visita, observacoes
metas_vendedor     → id, vendedor_id (FK), mes, ano, valor_meta,
                     bonus_valor, meta_ativacao, meta_n_clientes,
                     bonus_expansao_valor
```

### Módulo Financeiro
```
contas_bancarias        → id, nome, tipo (BANCO/DINHEIRO/CHEQUE), ativo
categorias_financeiras  → id, nome, tipo (PAGAR/RECEBER), cor_hex
compras_financeiras     → id, fornecedor, descricao, valor_total,
                          data_compra, nf_pdf_path, created_at
vendas_financeiras      → id, cliente, descricao, valor_total,
                          data_venda, nf_pdf_path, created_at
lancamentos             → id, tipo (PAGAR/RECEBER), descricao, valor,
                          data_vencimento, data_pagamento, status,
                          parcela_numero, parcela_total,
                          conta_bancaria_id (FK), categoria_id (FK),
                          compra_id (FK), venda_id (FK),
                          recorrente (bool), recorrencia_origem_id
anexos_lancamento       → id, lancamento_id (FK), arquivo_path,
                          tipo (BOLETO/NF), nome_original, created_at
saldo_inicial_conta     → id, conta_bancaria_id (FK), mes, ano, valor
                          UNIQUE (conta_bancaria_id, mes, ano)
metas_mensais           → id, mes, ano, valor_meta, tipo, descricao
                          UNIQUE (mes, ano, tipo)
```

---

## Fórmulas e regras de negócio críticas

```python
# Consumo de tecido
metros = peso_kg * 1000 / (gramatura * largura_cm / 100)

# Precificação Simples Nacional
preco_venda = custo_base / (1 - aliquota - margem)

# Comissão vendedor
comissao = total_pedido * tabela.comissao_pct

# Bônus logística
bonus_logistica = bonus_valor if total_mes >= meta_ativacao else 0

# Bônus expansão
bonus_expansao = floor(novos_clientes / meta_n) * bonus_valor

# Camadas de corte
camadas = min(ceil(qtd / pecas_por_enfesto), max_camadas)
```

---

## Regras de desenvolvimento (para Claude Code)

1. Sempre especificar quais arquivos ler (máx 3-4 por prompt)
2. Sempre pedir para ler antes de escrever — nunca assumir nomes de variáveis
3. Usar `/compact` entre sessões longas
4. `.claudeignore` ignora: `node_modules/`, `uploads/`
5. **Sem azul no CSS** — usar apenas neutros quentes + cor principal definida
6. PDFs: A4, preto e branco, com logo da empresa
7. Comando Python: sempre `py -3.12 -m` (não `python` nem `py -3.11`)
8. CLAUDE.md na raiz mantém contexto entre sessões
