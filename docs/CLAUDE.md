# CLAUDE.md — Contexto do SmartCut para Claude Code

> Leia este arquivo no início de CADA sessão de desenvolvimento.
> Atualizado em: Setembro 2026

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
- PDFs: ReportLab (A4, preto e branco, com logo); relatórios HTML/Jinja2 em
  `relatorios/` (relVen001 pedido, relPro001 ficha de corte)
- Encaixe: spyrrow + OR-Tools CP-SAT, embutido no backend (`services/nesting_v2/`)
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
- `uploads/`

---

## Módulos implementados

| Módulo | Status | Localização |
|---|---|---|
| Tecidos | ✅ Completo | CADASTROS → Tecidos |
| Moldes | ⚠️ Funcional com bugs | CADASTROS → Moldes |
| Encaixe Rápido | ✅ Completo | PRODUÇÃO → Encaixe Rápido |
| Encaixes | ✅ Completo | PRODUÇÃO → Encaixes |
| Ordem de Corte | ✅ Completo | Pedido → Ordem de Corte |
| Pedidos de Venda | ⚠️ Bugs conhecidos | VENDAS → Pedidos |
| Precificação | ✅ Completo | GESTÃO → Precificação |
| Projeção | ✅ Completo | GESTÃO → Projeção |
| Configurações | ✅ Completo | Footer → ⚙ |
| Painel Vendedor | 🔄 Em desenvolvimento | /vendedor |
| Financeiro | 🔄 Em desenvolvimento | FINANCEIRO |

---

## Produção — motor, enfesto e plano de corte

Detalhes em `docs/FUNCIONALIDADES.md` (PRODUÇÃO). O essencial:

- **Motor único v2** (spyrrow + OR-Tools). O v1 (Node.js) foi removido — não
  existe seletor nem motor reserva. Boot loga `Motor v2 disponível`.
- **Tipo de corte do molde** (obrigatório): `simples` · `par` (2 espelhadas no
  enfesto simples, iguais no duplo) · `par_sem_espelho` (2 iguais, nunca
  espelhadas). Aviso de simetria na tela de moldes.
- **Enfesto** decidido pelo sistema (`nesting_v2/decisor.py`): "Enfesto simples"
  (MESMA_FACE) / "Enfesto duplo" (FACE_A_FACE) — nomes da produção só na
  interface. Empate < 1%: sem sobra → menos mesas → regras da produção
  (forrado `produtos.dupla_camada` → duplo; 2–3 camadas → simples; senão duplo).
- **Qualidade Automática** = orçamento de tempo da OC
  (`planejamento/custo.py`, Configurações > Produção, 300 s).
- **Organizar o corte** (`ordens_corte.organizar_por`): PRODUTO (padrão) usa o
  plano de corte multicor (`planejamento/plano_corte.py`, tolerância de tecido
  2%, cores do mesmo tecido até 5 cm de largura, sobra só se inevitável);
  COR é o fluxo antigo por lote (`_agrupar_por_lote` + `_montar_todos`).
- **Estoque por cor**: encaixe multicor tem uma linha por lote em
  `encaixe_camadas`; reserva/baixa/estorno somam por essas linhas
  (`Encaixe.consumo_por_lote`). Nunca somar `Encaixe.lote_id × peso` direto.
- **Ficha de corte**: `relatorios/producao/relPro001.html` e `_basico` — por
  produto quando a OC é PRODUTO, lista de mesas quando é COR.
- **Testes de OC real só em banco de CÓPIA** (`SMARTCUT_DB_PATH` apontando para
  uma cópia de `backend/smartcut.db`; ver `scripts/medir_oc.py`). O backend dev
  com `--reload` aplica migrations novas no boot — faça backup antes de criar
  uma.

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
