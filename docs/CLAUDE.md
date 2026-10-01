# CLAUDE.md — Regras para agentes de código

Leia antes de qualquer alteração. Como o sistema funciona:
[SISTEMA.md](SISTEMA.md). Setup, testes e build:
[DESENVOLVIMENTO.md](DESENVOLVIMENTO.md). Antes de qualquer mudança estrutural
(banco, instalação, módulos, autenticação, API, idiomas), consultar
[ARQUITETURA.md](ARQUITETURA.md).

SmartCut: Electron + React 18 (Vite, CSS Modules) + FastAPI (Python 3.12,
SQLAlchemy 2, Alembic) + SQLite. Sistema de gestão da Vaidosa Fitness.

## Ambiente
- Python **sempre** `py -3.12 -m ...` (nunca `python`, `pip` solto ou outra versão).
- Backend: `cd backend && py -3.12 -m uvicorn main:app --reload` · Frontend: `cd frontend && npm run dev`.

## Código
- Ler antes de escrever; usar os nomes exatos que já existem (não renomear).
- Backend em camadas: `routers/` (respostas `{"data": ..., "error": ...}`) →
  `services/` → `models/`; ids UUID; permissões por `require_permission(modulo, acao)`.
- Erro de negócio novo usa `ErroApp` com código (ex.: `OC_STATUS_MUDOU`) e
  params (`services/erros.py`); nunca `HTTPException` com texto solto.
- Frontend: uma função por rota em `src/api/`; sem dependência nova sem necessidade.
- Antes de terminar: `ruff check`/`ruff format` + pytest no backend; `npm run lint`,
  `npm test` e `npm run build` no frontend.

## Interface
- **Sem azul.** Neutros (preto, branco, cinzas); ver variáveis em `styles/variables.css`
  e `global.css` antes de criar outra.
- **Maiúsculo real**: campo em maiúsculo usa a classe `.sc-upper` **e** converte o
  valor no `onChange` (`.toUpperCase()` ou `upperOnChange` de `utils/uppercase.js`) —
  nunca só CSS. Sem maiúsculo: login, senhas, e-mail, URLs e buscas.
- Documentos impressos: A4, preto e branco, logo da empresa; novos relatórios são
  modelos Jinja em `relatorios/` (não ReportLab).

## Dados do usuário
- Arquivo do usuário (anexo, logo, NF-e, moldes, catálogos, certificado) **sempre**
  pela pasta de dados: `services/pasta_dados.py` (`pasta_uploads()`, `resolver()`,
  `relativo()`). O banco guarda caminho relativo. Nunca `open("uploads/...")` nem
  caminho relativo ao diretório atual.
- Nunca mexer em `%APPDATA%\smartcut`, em `backend/smartcut.db` sem backup, nem nos
  modelos de `relatorios/` sem pedido explícito.

## Banco e migrations
- Mudança de schema = migration Alembic nova em `backend/alembic/versions/`, revisada à mão.
- **Nunca editar uma migration já aplicada.**
- **Backup do banco antes de criar migration**: o backend com `--reload` aplica a
  migration nova no boot.
- **Testes com dados reais só em cópia do banco** (`SMARTCUT_DB_PATH` apontando para a
  cópia; `scripts/medir_oc.py`). Os testes automáticos já usam banco e pasta temporários.
- **Antes de qualquer comando alembic, conferir o caminho do banco impresso no início**
  (`[alembic] banco alvo: ...`). Downgrade só roda com `SMARTCUT_PERMITIR_DOWNGRADE=1`.

## Regras de negócio que não mudam sem decisão explícita
```python
metros = peso_kg * 1000 / (gramatura * largura_cm / 100)
preco_venda = custo_base / (1 - aliquota - margem)
comissao = total_pedido * tabela.comissao_pct
bonus_logistica = bonus_valor if total_mes >= meta_ativacao else 0
bonus_expansao = floor(novos_clientes / meta_n) * bonus_valor
camadas = min(ceil(qtd / pecas_por_enfesto), max_camadas)
```
- Peso/custo/metros de um `Encaixe` são de **uma camada** (× `num_camadas`).
- Estoque de encaixe multicor soma as linhas de `encaixe_camadas`
  (`Encaixe.consumo_por_lote`), nunca `lote_id × peso` direto.
- Tipo de corte (`simples` / `par` / `par_sem_espelho`) e a decisão de enfesto:
  ver SISTEMA.md, seção d.

## Não ler / não modificar
`node_modules/`, `uploads/`, `backend/build/`, `backend/dist/`, `release/`,
`electron/bin/` (ver `.claudeignore`).
