# SmartCut — Roadmap e Visão de Produto

> **DESCARTADO.** Este plano não vale mais: o SmartCut **não terá versão web,
> SaaS nem multiempresa**. Tudo roda instalado na máquina do cliente. O
> documento fica só como registro histórico; o estado atual e os próximos
> passos estão em [../SISTEMA.md](../SISTEMA.md).

## Visão do Produto

O SmartCut nasceu como um sistema interno de gestão de corte têxtil para a Vaidosa Fitness.
A visão futura é transformá-lo em um **produto SaaS** (Software as a Service) comercializável
para outras confecções do Brasil, mantendo toda a robustez construída internamente.

---

## Estágio atual — Fase 1: MVP Interno

**Status:** Em produção (localhost)
**Objetivo:** Sistema funcional para a Vaidosa Fitness

O que está funcionando:
- Gestão completa de tecidos, moldes e encaixes
- Pedidos de venda com PDF automático
- Precificação detalhada de produtos
- Motor de nesting para otimização de corte
- Painel de vendedores (em desenvolvimento)

**Limitações atuais (intencionais para MVP):**
- Roda apenas localmente (localhost)
- Sem autenticação para o gestor
- Uma única empresa no banco (single-tenant)
- Sem HTTPS

---

## Estágio futuro — Fase 2: Deploy Web (próximos 3-6 meses)

**Objetivo:** Colocar o SmartCut na web para acesso remoto

### O que precisa ser feito:

**Backend:**
- [ ] Deploy em servidor cloud (Render, Railway ou VPS)
- [ ] Configurar HTTPS com certificado SSL
- [ ] Variáveis de ambiente para produção
- [ ] CORS configurado para domínio real
- [ ] Banco PostgreSQL em servidor cloud

**Frontend:**
- [ ] Build de produção do React (npm run build)
- [ ] Deploy frontend em CDN (Vercel, Netlify ou GitHub Pages)
- [ ] Configurar domínio customizado (smartcut.com.br)
- [ ] Layout responsivo completo (mobile + desktop)

**Autenticação:**
- [ ] Login para o gestor (hoje sem login)
- [ ] JWT para vendedores (já implementado)
- [ ] Recuperação de senha por email

### Arquitetura de deploy:

```
smartcut.com.br          → Frontend (Vercel/Netlify)
api.smartcut.com.br      → Backend FastAPI (Render/VPS)
db.smartcut.com.br       → PostgreSQL (Render/Supabase)
```

---

## Estágio futuro — Fase 3: Produto SaaS (6-12 meses)

**Objetivo:** Vender o SmartCut para outras confecções

### Mudanças de arquitetura necessárias:

**Multi-tenancy (CRÍTICO):**
Hoje o banco serve uma empresa. Para SaaS, cada cliente é isolado.

```sql
-- Adicionar em TODAS as tabelas:
empresa_id UUID NOT NULL REFERENCES empresas(id)

-- Nova tabela empresas:
CREATE TABLE empresas (
  id UUID PRIMARY KEY,
  nome VARCHAR(200),
  cnpj VARCHAR(20) UNIQUE,
  plano VARCHAR(20),  -- free, basic, pro, enterprise
  ativo BOOLEAN DEFAULT true,
  criado_em TIMESTAMP DEFAULT NOW()
);

-- Nova tabela usuarios_gestor:
CREATE TABLE usuarios_gestor (
  id UUID PRIMARY KEY,
  empresa_id UUID REFERENCES empresas(id),
  nome VARCHAR(100),
  email VARCHAR(100) UNIQUE,
  senha_hash VARCHAR(200),
  role VARCHAR(20),  -- admin, gestor, operador
  criado_em TIMESTAMP DEFAULT NOW()
);
```

**Planos e limites:**

| Recurso | Free | Basic (R$99/mês) | Pro (R$299/mês) | Enterprise |
|---------|------|-----------------|-----------------|------------|
| Pedidos/mês | 50 | 500 | Ilimitado | Ilimitado |
| Vendedores | 2 | 10 | Ilimitado | Ilimitado |
| Armazenamento | 1GB | 10GB | 50GB | 200GB |
| Suporte | Email | Chat | Prioritário | Dedicado |
| Nesting avançado | ❌ | ✅ | ✅ | ✅ |
| Multi-usuário | ❌ | ✅ | ✅ | ✅ |

**Novos módulos necessários:**
- [ ] Página de marketing/landing (smartcut.com.br)
- [ ] Sistema de cadastro de nova empresa (onboarding)
- [ ] Integração com gateway de pagamento (Stripe ou Pagar.me)
- [ ] Painel master admin (você gerencia todos os clientes)
- [ ] Sistema de faturamento automático
- [ ] Métricas de uso por empresa

### Estrutura de pastas para SaaS:

```
SmartCut/
├── backend/              ← API (já existe, adaptar)
├── frontend/             ← Sistema de gestão (já existe, adaptar)
├── landing/              ← NOVO: página de marketing
│   ├── index.html
│   ├── precos.html
│   └── contato.html
└── admin/                ← NOVO: painel master
    └── src/
```

---

## Estágio futuro — Fase 4: App Mobile Nativo (12+ meses)

**Objetivo:** App dedicado para vendedores e gestores

- React Native ou Expo
- iOS + Android
- Push notifications para metas e comissões
- Câmera para registrar visitas de clientes
- Assinatura digital de pedidos
- Modo offline com sincronização

---

## Prioridades imediatas (AGORA)

### 1. Painel do Vendedor funcionando (esta semana)
- Login com logo da empresa
- Dashboard de metas motivador
- Pedidos agrupados por mês
- Catálogos para download/WhatsApp
- Leads com mapa

### 2. Deploy web básico (próximo mês)
- Backend no Render.com (gratuito)
- Frontend no Vercel (gratuito)
- URL real: smartcut.com.br (subdomínio)
- HTTPS automático

### 3. Login para o gestor (junto com deploy)
- Simples: email + senha
- Protege o sistema de gestão na web

---

## Decisões técnicas já tomadas (manter)

| Decisão | Justificativa para SaaS |
|---------|------------------------|
| FastAPI (Python) | Alta performance, fácil de escalar |
| PostgreSQL | Suporta multi-tenant com RLS (Row Level Security) |
| React | Fácil adicionar responsividade e PWA |
| JWT | Padrão para APIs SaaS |
| CSS Modules | Sem dependência de framework pesado |
| ReportLab | Geração de PDF server-side (melhor para SaaS) |

---

## O que NÃO precisa mudar para o SaaS

- A lógica de negócio (nesting, precificação, pedidos) está bem desenhada
- A estrutura de routers FastAPI escala bem
- O design system pode ser mantido
- Os modelos do banco só precisam do campo `empresa_id`

---

## Custo estimado de infraestrutura (SaaS)

| Serviço | Plano | Custo/mês |
|---------|-------|-----------|
| Render (backend) | Starter | R$ 25 |
| Render (PostgreSQL) | Starter | R$ 25 |
| Vercel (frontend) | Pro | R$ 50 |
| Domínio | .com.br | R$ 5 |
| **Total mínimo** | | **~R$ 105/mês** |

Com 5 clientes pagando R$99/mês = R$495 → já cobre a infra com lucro.

---

## Próximos passos imediatos

1. ✅ Terminar painel do vendedor (prioridade atual)
2. ⬜ Deploy web (Render + Vercel)
3. ⬜ Login para gestor
4. ⬜ Adicionar empresa_id nas tabelas (preparar multi-tenant)
5. ⬜ Landing page do SmartCut
6. ⬜ Sistema de cadastro de clientes
