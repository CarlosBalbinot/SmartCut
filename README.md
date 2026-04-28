# SmartCut

**Sistema inteligente de gestão e otimização de corte têxtil.**

O SmartCut automatiza o planejamento de produção em confecções — desde o cadastro de tecidos e moldes até a geração do mapa de encaixe e relatório de corte para o cortador. O objetivo é maximizar o aproveitamento de matéria-prima e eliminar cálculos manuais.

---

## Stack tecnológica

| Camada | Tecnologia |
|--------|-----------|
| Frontend | React 18 + Vite + CSS Modules |
| Backend | Python 3.11 + FastAPI |
| ORM | SQLAlchemy 2.x + Alembic |
| Banco de dados | PostgreSQL 15+ |
| Parser de moldes | ezdxf (DXF), custom (PLT/ADS) |
| Motor de nesting | Node.js (skyline packer) |
| Relatórios | ReportLab (PDF) |
| Visualizador | Konva.js |

---

## Estrutura de pastas

```
SmartCut/
├── README.md
├── CLAUDE.md                        ← contexto do projeto para Claude Code
├── .env                             ← variáveis de ambiente (não versionar)
├── .env.example                     ← modelo do .env
├── docker-compose.yml
│
├── backend/
│   ├── main.py                      ← entry point FastAPI
│   ├── config.py                    ← configurações via pydantic-settings
│   ├── database.py                  ← engine SQLAlchemy + get_db()
│   ├── requirements.txt
│   │
│   ├── alembic/                     ← migrations do banco
│   │   ├── env.py
│   │   └── versions/
│   │
│   ├── models/                      ← modelos ORM (tabelas)
│   │   ├── modelo_tecido.py         ← modelo de tecido (Maxxi, Wish...)
│   │   ├── cor_tecido.py            ← cor por modelo (Preto, Marrom...)
│   │   ├── lote_tecido.py           ← rolo/lote com rastreio de consumo
│   │   ├── grupo_molde.py           ← grupo de peças (Legging, Top...)
│   │   ├── molde.py                 ← peça individual com geometria
│   │   ├── pedido.py                ← pedido de produção
│   │   ├── pedido_peca.py           ← peças e quantidades por tamanho
│   │   ├── pedido_tecido.py         ← tecidos vinculados ao pedido
│   │   └── encaixe.py               ← resultado do nesting
│   │
│   ├── schemas/                     ← validação Pydantic
│   ├── routers/                     ← endpoints REST
│   ├── services/                    ← lógica de negócio
│   │   ├── nesting_service.py       ← orquestra o motor de nesting
│   │   ├── gramatura_service.py     ← converte peso ↔ metros
│   │   ├── report_service.py        ← gera PDF do relatório de corte
│   │   └── lote_service.py          ← controle de estoque por lote
│   │
│   ├── parsers/                     ← leitura de arquivos de molde
│   │   ├── dxf_parser.py
│   │   ├── plt_parser.py            ← suporte a HP-GL/2 PE encoding
│   │   └── ads_parser.py            ← Audaces (parcial)
│   │
│   └── nesting/
│       ├── nest_worker.js           ← motor Node.js (skyline packer)
│       └── nesting_bridge.py        ← ponte Python → Node.js
│
└── frontend/
    ├── index.html
    ├── vite.config.js               ← proxy /api → :8000
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── styles/
        │   ├── variables.css        ← design system (tokens de cor)
        │   └── index.css
        ├── services/
        │   └── api.js               ← todas as chamadas à API centralizadas
        ├── components/              ← componentes reutilizáveis
        │   ├── Modal/
        │   ├── Toast/               ← notificações do sistema
        │   ├── GrupoAccordion/      ← accordion de moldes
        │   └── PecaCard/            ← card de peça na importação
        └── pages/
            ├── TecidosPage.jsx
            ├── MoldesPage.jsx
            ├── PedidosPage.jsx
            ├── PedidoDetalhePage.jsx
            ├── EncaixesPage.jsx
            └── EncaixePage.jsx
```

---

## Pré-requisitos

- Node.js 18+
- Python 3.11+
- PostgreSQL 15+

---

## Como rodar o projeto

### 1. Clonar e configurar o ambiente

```bash
git clone <repositorio>
cd SmartCut
copy .env.example .env
```

Editar o `.env` com suas configurações:

```env
DATABASE_URL=postgresql://postgres:root@localhost:8844/smartcut_db
SECRET_KEY=smartcut-secret-key-2024
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=50
NESTING_TIMEOUT_SEC=120
```

### 2. Banco de dados

Criar o banco `smartcut_db` no PostgreSQL (via pgAdmin ou linha de comando):

```sql
CREATE DATABASE smartcut_db;
```

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
copy .env.example .env    # copiar o .env para dentro do backend também

# Criar as tabelas
alembic upgrade head

# Rodar o servidor
uvicorn main:app --reload
```

Backend disponível em: `http://localhost:8000`
Documentação da API: `http://localhost:8000/docs`

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Sistema disponível em: `http://localhost:5173`

---

## Fases do projeto

### ✅ Fase 1 — Infraestrutura (concluída)

- Estrutura de pastas backend e frontend
- Banco PostgreSQL com todas as tabelas e migrations via Alembic
- API FastAPI com CRUD completo de todos os módulos
- Frontend React com roteamento e design system próprio
- Sistema de notificações (Toast) e modais reutilizáveis

### ✅ Fase 2 — Cadastros (concluída)

**Tecidos**
- Hierarquia: Modelo → Cor → Lote/Rolo
- Cada lote tem: peso inicial, peso disponível, valor/kg, data de compra, status
- Alerta automático quando lote atinge ≤ 5kg
- Histórico de lotes esgotados/arquivados
- Rastreio de consumo por pedido

**Moldes**
- Importação de arquivos PLT (HP-GL/2 PE encoding), DXF e ADS
- Preview visual das peças extraídas do arquivo
- Suporte a arquivos com graduação (P ao GG) — agrupamento automático por área
- Por peça: nome, tipo de corte (simples/par/par sem espelho), sentido do fio livre com linha arrastável, flip horizontal/vertical
- Organização hierárquica: Grupo → Parte → Tamanho
- Edição posterior de qualquer propriedade

### ✅ Fase 3 — Pedidos (concluída)

- Numeração automática sequencial (editável)
- Múltiplos tecidos por pedido (com lote recomendado automaticamente)
- Adição de peças por grupo + tamanho + quantidade + tecido específico
- Cálculo automático de moldes necessários (considerando tipo de corte par)
- Resumo do corte agrupado por tecido com: metros estimados, peso, custo
- Status com histórico: Rascunho → Em produção → Concluído
- Exclusão com confirmação

### ✅ Fase 4 — Nesting e Relatórios (parcialmente concluída)

- Motor de nesting em Node.js (skyline bottom-left packer)
- Cálculo automático de camadas por enfesto (respeitando máx. do tecido)
- Limite de 130cm de comprimento por enfesto
- Criação automática de múltiplos enfestos quando necessário
- Visualizador Konva.js do mapa de encaixe
- Geração de PDF com ReportLab (relatório de corte para o cortador)

### ⬜ Fase 5 — Nesting avançado (pendente)

- Substituir algoritmo atual por SVGnest real (algoritmo genético)
- Respeitar sentido do fio livre (ângulo em graus) no posicionamento
- Aplicar flip_horizontal e flip_vertical de cada peça
- Reduzir desperdício de ~58% para <20%

### ⬜ Fase 6 — Defeitos no tecido (pendente)

- Cortador informa coordenadas de furos/manchas no rolo
- Sistema cria zonas de exclusão no plano de corte
- Algoritmo de nesting desvia os moldes das zonas proibidas

### ⬜ Fase 7 — Dashboard e controle de estoque (pendente)

- Dashboard inicial com resumo operacional
- Baixa automática de estoque ao confirmar encaixe
- Relatório de perdas e retalhos por período
- Histórico de aproveitamento por modelo de tecido

---

## Regras de negócio principais

**Conversão gramatura → metros**
```
metros = peso_kg × 1000 / (gramatura_g_m2 × largura_util_cm / 100)
```

**Recomendação de lote**
O sistema sempre sugere o lote já aberto mais antigo antes de sugerir um lote intacto.

**Cálculo de camadas**
```
camadas = ceil(quantidade_pedido / peças_por_enfesto)
camadas = min(camadas, max_camadas_do_tecido)
```

**Alerta de estoque**
Lotes com peso_disponivel_kg ≤ 5kg geram alerta visual em toda a interface.

---

## Padrões de desenvolvimento

- **Backend:** type hints em todas as funções, schemas Pydantic em todos os endpoints, lógica de negócio apenas em services (nunca nos routers)
- **Frontend:** componentes funcionais com hooks, chamadas à API centralizadas em `src/services/api.js`, CSS Modules para escopo de estilo
- **API:** prefixo `/api/v1/`, resposta padrão `{ data, error }`, status HTTP corretos
- **Banco:** migrations via Alembic, nunca deletar registros (soft delete com status)