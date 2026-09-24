# ESTRUTURA.md — Arquitetura e Stack Técnica

## Stack tecnológica

| Camada | Tecnologia | Versão |
|---|---|---|
| Frontend | React + Vite + CSS Modules | React 18 |
| Backend | Python + FastAPI | Python 3.12 |
| Banco de dados | PostgreSQL | 15+ |
| ORM | SQLAlchemy + Alembic | 2.x |
| PDFs | ReportLab | — |
| Gráficos | Recharts | — |
| Autenticação | JWT | Painel vendedor |
| Nesting (provisório) | Node.js skyline packer | — |
| Nesting (futuro) | Deepnest C++ | via Docker/WSL |
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
│   │   └── nesting/
│   │       └── engine/          # Deepnest C++ (compilar para Windows)
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
├── .claudeignore                # node_modules/, svgnest/, uploads/
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

### Módulo Encaixes
```
encaixes           → id, nome, tecido_largura_cm, tecido_comprimento_cm,
                     eficiencia_pct, svg_resultado, created_at
```

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
4. `.claudeignore` ignora: `node_modules/`, `svgnest/`, `uploads/`
5. **Sem azul no CSS** — usar apenas neutros quentes + cor principal definida
6. PDFs: A4, preto e branco, com logo da empresa
7. Comando Python: sempre `py -3.12 -m` (não `python` nem `py -3.11`)
8. CLAUDE.md na raiz mantém contexto entre sessões
