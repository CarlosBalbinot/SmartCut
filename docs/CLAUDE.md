# CLAUDE.md — Contexto do SmartCut para Claude Code

> Leia este arquivo no início de CADA sessão de desenvolvimento.
> Atualizado em: Junho 2026

---

## O projeto

SmartCut é um sistema de gestão têxtil desenvolvido para a Vaidosa Fitness
(Guaporé/RS, Brasil). Futuro: SaaS para confecções de pequeno e médio porte.

Desenvolvido por Carlos e Valdemir.

---

## Como rodar

```bash
# Backend (Python 3.12 — SEMPRE usar py -3.12)
cd backend
py -3.12 -m uvicorn main:app --reload
# http://localhost:8000/docs

# Frontend
cd frontend
npm run dev
# http://localhost:5173
```

**ATENÇÃO**: Nunca usar `python` ou `py -3.11`. Sempre `py -3.12 -m`.

---

## Banco de dados

```
PostgreSQL 15+
Host: localhost
Porta: 8844  ← porta não padrão, sempre especificar
User: postgres
Password: root
Database: smartcut
```

---

## Stack

- Frontend: React 18 + Vite + CSS Modules
- Backend: Python 3.12 + FastAPI
- ORM: SQLAlchemy 2.x + Alembic
- PDFs: ReportLab (A4, preto e branco, com logo)
- Gráficos: Recharts
- Auth: JWT (apenas painel vendedor)

---

## Regras de desenvolvimento — OBRIGATÓRIAS

### Para cada prompt:
1. **Máximo 3-4 arquivos para ler** por prompt
2. **Sempre ler antes de escrever** — nunca assumir nomes de variáveis, imports ou estruturas
3. **Usar nomes exatos** encontrados nos arquivos — não renomear
4. Usar `/compact` entre sessões longas

### CSS:
- **SEM AZUL** — nunca usar tons de azul
- Usar neutros: preto, branco, cinzas
- Cor principal do sistema: a definir (será aplicada em botões, badges, destaques)
- Não criar novas variáveis CSS sem verificar as existentes em `global.css`
- Maiúsculo real: campos em maiúsculo usam .sc-upper +
  onChange .toUpperCase() (nunca só CSS). Exceções sem
  maiúsculo: login, senhas, e-mail, URLs, buscas

### PDFs:
- Sempre A4
- Preto e branco
- Com logo da empresa (buscar caminho em `configuracao_empresa.logo_path`)

### Fórmulas críticas (nunca alterar):
```python
metros = peso_kg * 1000 / (gramatura * largura_cm / 100)
preco_venda = custo_base / (1 - aliquota - margem)
comissao = total_pedido * tabela.comissao_pct
bonus_logistica = bonus_valor if total_mes >= meta_ativacao else 0
bonus_expansao = floor(novos_clientes / meta_n) * bonus_valor
camadas = min(ceil(qtd / pecas_por_enfesto), max_camadas)
```

---

## .claudeignore

Os seguintes diretórios são ignorados — não ler, não modificar:
- `node_modules/`
- `svgnest/`
- `uploads/`

---

## Módulos implementados

| Módulo | Status | Localização |
|---|---|---|
| Tecidos | ✅ Completo | CADASTROS → Tecidos |
| Moldes | ⚠️ Funcional com bugs | CADASTROS → Moldes |
| Encaixe Rápido | ✅ Completo | PRODUÇÃO → Encaixe Rápido |
| Encaixes | ⚠️ Motor provisório | PRODUÇÃO → Encaixes |
| Pedidos de Venda | ⚠️ Bugs conhecidos | VENDAS → Pedidos |
| Precificação | ✅ Completo | GESTÃO → Precificação |
| Projeção | ✅ Completo | GESTÃO → Projeção |
| Configurações | ✅ Completo | Footer → ⚙ |
| Painel Vendedor | 🔄 Em desenvolvimento | /vendedor |
| Financeiro | 🔄 Em desenvolvimento | FINANCEIRO |

---

## Próximas implementações (ordem)

1. **Corrigir bug 422 em POST /financeiro/metas**
2. **Electron** — migração para app desktop (ver `docs/ELECTRON.md`)
3. **Redesign** — aplicar cor principal (aguardando definição de cor)
4. **Melhorias Moldes** — alinhamento SVG, piques, margem de costura, tecido tubular

---

## Documentação completa

Todos os detalhes estão em `docs/`:
- `README.md` — visão geral do projeto
- `ESTRUTURA.md` — stack, banco, pastas, tabelas
- `FUNCIONALIDADES.md` — o que existe hoje
- `ROADMAP.md` — próximas funcionalidades e bugs
- `ELECTRON.md` — plano de migração desktop
- `MOLDES.md` — especificação do editor de moldes
- `FINANCEIRO.md` — especificação do módulo financeiro
