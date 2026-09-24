# SmartCut

**Sistema inteligente de gestão e otimização de corte têxtil e vendas para confecções.**

O SmartCut centraliza toda a operação da confecção — desde o cadastro de tecidos e moldes até a geração de encaixes, pedidos de venda, precificação e gestão completa da força de vendas com painel mobile para representantes.

---

## Stack tecnológica

| Camada | Tecnologia |
|--------|-----------|
| Frontend Desktop | React 18 + Vite + CSS Modules |
| Frontend Mobile | React 18 + Vite (rota separada, mobile first) |
| Backend | Python 3.12 + FastAPI |
| ORM | SQLAlchemy 2.x + Alembic |
| Banco de dados | PostgreSQL 15+ |
| Autenticação | JWT (apenas painel do vendedor) |
| Parser de moldes | ezdxf (DXF), custom (PLT/ADS) |
| Motor de nesting | Node.js (skyline packer → futuro: Deepnest C++) |
| Relatórios | ReportLab (PDF) |
| Visualizador | Konva.js |
| Gráficos | Recharts |

---

## Estrutura de pastas

```
SmartCut/
├── README.md
├── CLAUDE.md
├── .env
├── .env.example
├── docker-compose.yml
│
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── requirements.txt
│   ├── alembic/
│   │   └── versions/
│   ├── models/
│   │   ├── modelo_tecido.py
│   │   ├── cor_tecido.py
│   │   ├── lote_tecido.py
│   │   ├── grupo_molde.py
│   │   ├── molde.py
│   │   ├── pedido.py
│   │   ├── encaixe.py
│   │   ├── precificacao.py
│   │   ├── venda.py           ← pedidos de venda, itens, tabelas, vendedores
│   │   ├── usuario.py         ← autenticação JWT para vendedores
│   │   ├── catalogo.py        ← catálogos PDF por tabela de preço
│   │   └── lead.py            ← leads/prospecção por vendedor
│   ├── schemas/
│   ├── routers/
│   │   ├── auth.py            ← POST /api/v1/vendedor/login
│   │   ├── vendedor_painel.py ← rotas do painel mobile do vendedor
│   │   └── ...outros routers
│   ├── services/
│   │   ├── nesting_service.py
│   │   ├── gramatura_service.py
│   │   ├── report_service.py
│   │   ├── lote_service.py
│   │   ├── precificacao_service.py
│   │   ├── venda_service.py
│   │   ├── pdf_venda_service.py
│   │   └── auth_service.py    ← geração e validação de JWT
│   ├── parsers/
│   │   ├── dxf_parser.py
│   │   ├── plt_parser.py
│   │   └── ads_parser.py
│   └── nesting/
│       ├── nest_worker.js
│       ├── nesting_bridge.py
│       └── engine/            ← Deepnest C++ (futuro)
│           └── Release/addon.node
│
└── frontend/
    ├── index.html
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx             ← sistema de gestão (desktop, sem login)
        ├── AppVendedor.jsx     ← painel do vendedor (mobile, com login JWT)
        ├── styles/
        │   ├── variables.css
        │   └── index.css
        ├── services/
        │   └── api.js
        ├── components/
        │   ├── Modal/
        │   ├── Toast/
        │   ├── GrupoAccordion/
        │   └── PecaCard/
        └── pages/
            ├── [páginas do sistema de gestão — desktop]
            └── vendedor/
                ├── LoginPage.jsx
                ├── DashboardVendedorPage.jsx
                ├── CatalogosPage.jsx
                ├── PedidosVendedorPage.jsx
                └── LeadsPage.jsx
```

---

## Pré-requisitos

- Node.js 18+
- Python 3.12+
- PostgreSQL 15+

---

## Como rodar o projeto

### 1. Clonar e configurar

```bash
git clone <repositorio>
cd SmartCut
copy .env.example .env
```

Editar o `.env`:

```env
DATABASE_URL=postgresql://postgres:root@localhost:8844/smartcut_db
SECRET_KEY=smartcut-secret-key-2024
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=50
NESTING_TIMEOUT_SEC=120
JWT_SECRET=smartcut-jwt-secret-2024
JWT_EXPIRE_HOURS=24
```

### 2. Banco de dados

```sql
CREATE DATABASE smartcut_db;
```

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn main:app --reload
```

Backend: `http://localhost:8000`
Docs: `http://localhost:8000/docs`

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Sistema de gestão (desktop): `http://localhost:5173`
Painel do vendedor (mobile): `http://localhost:5173/vendedor`

---

## Dois sistemas em uma base

### Sistema de Gestão — desktop, sem login
Acessado pelo gestor (Carlos) direto pela URL raiz.
Menu completo com todos os módulos de produção, vendas e gestão.

### Painel do Vendedor — mobile first, com login JWT
Rota separada `/vendedor`. Login com usuário e senha criados pelo gestor.
Layout responsivo otimizado para celular.
Cada vendedor vê apenas suas informações, catálogos e leads atribuídos.

---

## Módulos do sistema de gestão

### CADASTROS
- **Tecidos** — modelos, cores e lotes com rastreio de consumo
- **Moldes** — importação PLT/DXF/ADS com código de referência

### PRODUÇÃO
- **Encaixe Rápido** — gerar encaixe ágil sem criar pedido completo
- **Encaixes** — histórico de encaixes gerados

### VENDAS
- **Pedidos de Venda** — pedido completo com PDF comercial e PDF de corte

### GESTÃO
- **Precificação** — custo detalhado e preço de venda por produto
- **Projeção** — simulação de lucratividade com gráficos

### CONFIGURAÇÕES (footer do menu)
- **Dados da Empresa** — razão social, logo, contatos
- **Configurações Gerais** — alíquota, insumos, logística
- **Tabelas de Preço** — cadastro e gestão de tabelas com produtos e preços
- **Vendedores** — cadastro, credenciais, tabelas liberadas, metas e dashboard

---

## Fases do projeto

### ✅ Fase 1 — Infraestrutura (concluída)
- Banco PostgreSQL com migrations via Alembic
- API FastAPI com CRUD completo
- Frontend React com design system Apple-inspired (neutros quentes)
- Sistema de notificações Toast e modais reutilizáveis

### ✅ Fase 2 — Cadastros de Produção (concluída)

**Tecidos**
- Hierarquia: Modelo → Cor → Lote/Rolo
- Alerta automático ≤ 5kg, histórico de lotes esgotados

**Moldes**
- Importação PLT (HP-GL/2 PE), DXF, ADS
- Preview SVG das peças, graduação P ao GG
- Sentido do fio com linha arrastável em ângulo livre, flip horizontal/vertical
- Código de referência por grupo vinculado ao código de venda

### ✅ Fase 3 — Pedidos de Produção (concluída)
- Pedidos com múltiplos tecidos, peças por tamanho, resumo do corte
- Status: Rascunho → Em produção → Concluído

### ✅ Fase 4 — Nesting e Relatórios (parcialmente concluída)
- Motor Node.js skyline packer, limite 130cm, múltiplos enfestos
- Visualizador Konva.js, PDF de corte com ReportLab
- Encaixe Rápido: seleção ágil de tecidos e peças sem criar pedido

### ✅ Fase 5 — Precificação e Projeção (concluída)
- Custos detalhados: tecido, costura, linha overlock/reta, saquinho, caixa, gasolina
- Fórmula Simples Nacional em tempo real
- Projeção com gráficos Recharts (pizza, barras, margem)

### ✅ Fase 6 — Vendas (concluída)
- Pedidos de venda com tabela única de preço por pedido
- Preço unitário automático por tabela + condição (à vista / a prazo)
- PDF Formulário de Pedido e PDF Formulário de Corte
- Suporte a Plus Size (G1/G2/G3)
- Dashboard por vendedor: metas, comissões, gráficos

### ⬜ Fase 7 — Autenticação e Painel Mobile do Vendedor (pendente)

**Autenticação JWT**
- Tabela `usuarios` vinculada a `vendedores`
- Gestor cria usuário e senha para cada vendedor na tela de Configurações
- Login via POST /api/v1/vendedor/login → retorna JWT
- Rotas do painel protegidas por token
- Sistema de gestão desktop continua sem login

**Painel do Vendedor — rota `/vendedor` (mobile first)**

Dashboard de metas:
- Barra de progresso: total vendido no mês vs meta de ativação
- Card bônus logística: "Falta R$X para ganhar R$300"
- Card bônus expansão: "X de 5 novos clientes — falta Y"
- Total de comissão acumulada no mês
- Últimos 3 pedidos registrados

Catálogos:
- Lista de PDFs liberados pelo gestor especificamente para este vendedor
- Cada catálogo vinculado a uma tabela de preço
- Botão download + botão compartilhar (abre share nativo do celular / WhatsApp)

Pedidos:
- Lista dos pedidos registrados em nome deste vendedor
- Status de cada pedido
- Total e comissão por pedido

Leads:
- Lista de leads atribuídos manualmente pelo gestor a este vendedor
- Campos: nome do estabelecimento, endereço, telefone, observação
- Status: Novo / Visitado / Orçamento enviado / Não interessado / Cliente
- Botão "Traçar rota" → abre Google Maps com o endereço
- Botão "Registrar visita" → atualiza status com observação

**Gestão pelo gestor (em Configurações → Vendedores)**

Por vendedor:
- Usuário (login) e senha
- Tabelas de preço liberadas (checkboxes — cada vendedor tem acesso a tabelas específicas)
- Meta de ativação mensal (R$) — personalizada por vendedor
- Meta de novos clientes para bônus — personalizada
- Valor do bônus logística — personalizado
- Valor do bônus expansão — personalizado
- Pedido mínimo permitido (R$)

Catálogos:
- Upload de PDF por catálogo (nome + tabela vinculada)
- Atribuição manual: para cada catálogo, definir quais vendedores têm acesso
- Um mesmo catálogo pode ser liberado para múltiplos vendedores
- Um vendedor pode ter catálogos exclusivos

Leads:
- Gestor cadastra lead com: nome, endereço, cidade, telefone, segmento, observação
- Atribui manualmente a um vendedor específico
- Pode reatribuir a qualquer momento

### ⬜ Fase 8 — Nesting avançado com Deepnest (pendente)
- Motor C++ Deepnest via addon Node.js (compilar para Windows/Linux)
- NFP via Minkowski Sum para encaixe preciso de moldes irregulares
- Respeitar sentido do fio (ângulo livre em graus)
- Aplicar flip_horizontal e flip_vertical
- Reduzir desperdício de ~58% para < 20%

### ⬜ Fase 9 — Defeitos no tecido (pendente)
- Cortador informa coordenadas de furos/manchas
- Zonas de exclusão no plano de corte
- Nesting desvia automaticamente os moldes

### ⬜ Fase 10 — Dashboard e controle de estoque (pendente)
- Dashboard operacional completo
- Baixa automática de estoque ao confirmar encaixe
- Relatório de perdas e retalhos por período
- Analytics de performance comparativo entre vendedores

---

## Regras de negócio

**Conversão gramatura → metros**
```
metros = peso_kg × 1000 / (gramatura_g_m2 × largura_util_cm / 100)
```

**Precificação — Simples Nacional**
```
preco_venda = custo_base / (1 - aliquota - margem_desejada)
imposto = preco_venda × aliquota
lucro = preco_venda - custo_base - imposto
```

**Comissão de vendedor**
```
base = total dos itens no preço à vista ou a prazo (conforme condição do pedido)
comissao = base × tabela.comissao_pct
```

**Bônus logística**
```
if total_vendido_mes >= vendedor.meta_ativacao:
    bonus_logistica = vendedor.bonus_logistica_valor
```

**Bônus expansão**
```
novos_clientes = clientes que aparecem pela primeira vez nos pedidos do mês
bonus_expansao = floor(novos_clientes / vendedor.meta_novos_clientes) × vendedor.bonus_expansao_valor
```

**Recomendação de lote**
Sistema sugere lote aberto mais antigo antes de lote intacto.

**Cálculo de camadas**
```
camadas = min(ceil(qtd / pecas_por_enfesto), tecido.max_camadas)
```

**Alerta de estoque**
Lotes com `peso_disponivel_kg ≤ 5kg` geram alerta em toda a interface.

**Plus Size**
Grupos com `tem_plus=true` exibem colunas G1/G2/G3 em pedidos e PDFs.

**Tabela única por pedido**
Um pedido de venda usa uma única tabela de preço — não permite misturar.

**Catálogos por vendedor**
Cada catálogo é atribuído manualmente pelo gestor a vendedores específicos.
O vendedor só vê os catálogos que o gestor liberou para ele.

**Leads por vendedor**
Cada lead é atribuído manualmente pelo gestor a um vendedor específico.
O vendedor só vê leads atribuídos a ele.

---

## Padrões de desenvolvimento

- **Backend:** type hints, schemas Pydantic em todos os endpoints, lógica apenas em services
- **Frontend desktop:** CSS Modules, chamadas à API centralizadas em `api.js`
- **Frontend mobile:** componentes separados em `pages/vendedor/`, layout responsivo mobile first
- **Auth:** JWT no header `Authorization: Bearer <token>` nas rotas do painel do vendedor
- **API:** prefixo `/api/v1/`, resposta `{ data, error }`, status HTTP corretos
- **Banco:** soft delete com `status` ou `ativo`, nunca deletar registros de produção
- **PDFs:** ReportLab, A4, preto e branco, logo no cabeçalho
- **Gráficos:** Recharts, paleta de cinzas neutros
