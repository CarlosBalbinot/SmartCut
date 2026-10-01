"""Monta o banco de produção da v1.3.0 a partir de dois bancos SQLite.

A instalação de 28/09 carimbou a versão f8a6f7ef2ccf num banco antigo sem
criar a estrutura (faltam 16 das 48 tabelas da baseline) — a 1.3.0 não sobe
sobre ele. Este script gera um banco NOVO, na estrutura da head, com:

  - do banco INSTALADO: o financeiro (dados reais) e os arquivos dos anexos
    (anexo cujo arquivo não existe NÃO é copiado — entra como descartado no
    relatório; lançamentos e saldos não mudam);
  - do banco de DEV: os cadastros (empresa, configurações, produtos, grades,
    preços, moldes, tecidos, condições de pagamento, TES, transportadoras)
    e os arquivos que eles referenciam (moldes, logo da empresa).

Não copia: usuários/permissões, clientes, vendedores, lotes de tecido,
pedidos, notas fiscais, ordens de corte, encaixes e demais dados de teste —
o primeiro acesso do sistema cria o administrador.

Os bancos de entrada são abertos SOMENTE LEITURA (mode=ro). A pasta de saída
é recriada a cada execução: rodar de novo com os mesmos bancos gera o mesmo
resultado (linhas copiadas na ordem do rowid de origem).

Uso (de backend/):
    py -3.12 -m scripts.montar_banco_producao \\
        --instalado  <cópia do %APPDATA%\\smartcut\\smartcut.db> \\
        --dev        <cópia do backend\\smartcut.db> \\
        --base-instalado <pasta onde "uploads/financeiro/..." do instalado existe> \\
        --base-dev   <pasta onde "uploads/..." do dev existe (backend\\)> \\
        --saida      <pasta nova>

Saída: a pasta de dados do usuário pronta, na mesma estrutura de
%APPDATA%\\smartcut (ver backend/services/pasta_dados.py):
    <saida>/smartcut.db
    <saida>/uploads/financeiro/<lançamento>/...   anexos
    <saida>/uploads/logos/...                     logo
    <saida>/uploads/...                           moldes
    <saida>/Certificados/...                      certificado (se houver)
    <saida>/relatorio_montagem.txt
Os caminhos no banco ficam relativos a essa pasta ("uploads/...", com "/").
Instalação: com o SmartCut fechado, copiar o conteúdo de <saida> para
%APPDATA%\\smartcut.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── Plano de cópia ────────────────────────────────────────────────────────────
# Ordem = ordem de inserção (pais antes dos filhos, pelas chaves estrangeiras).

# Financeiro: lancamentos → contas_bancarias, categorias_financeiras,
# compras_financeiras, vendas_financeiras (e a si mesma: transferências);
# anexos_lancamento → lancamentos; saldo_inicial_conta → contas_bancarias.
DO_INSTALADO = [
    "contas_bancarias",
    "categorias_financeiras",
    "compras_financeiras",
    "vendas_financeiras",
    "lancamentos",
    "anexos_lancamento",
    "saldo_inicial_conta",
    "metas_mensais",
]

DO_DEV = [
    # empresa e configurações
    "empresa",
    "configuracao_empresa",
    "configuracao_custos_fixos",
    "configuracao_grade",
    # produtos, grades, preços (produtos → grupos_produto, tabelas_grade;
    # produtos_sku → produtos, itens_tabela_grade; precos_tabela_produto →
    # produtos, produtos_sku, tabelas_preco)
    "grupos_produto",
    "tabelas_grade",
    "linhas_grade",
    "colunas_grade",
    "itens_tabela_grade",
    "tabelas_preco",
    "produtos",
    "produtos_sku",
    "precos_tabela_produto",
    # moldes (grupos_molde → produtos; moldes → grupos_molde)
    "grupos_molde",
    "moldes",
    "precificacoes",
    "precos_referencia",
    # tecidos (cores_tecido → modelos_tecido); lotes NÃO (são de teste)
    "modelos_tecido",
    "cores_tecido",
    # fiscal / comercial
    "condicoes_pagamento",
    "tes",
    "transportadoras",
]

# configuracao_empresa existe com dados nos dois bancos. Decisão (30/09):
# linha do DEV (tem Configurações > Produção) com os valores reais do
# INSTALADO nestas colunas.
CONFIG_DO_INSTALADO = ("aliquota_simples", "custo_etiqueta")

# Tabelas com dados nos dois bancos que têm regra definida acima. Qualquer
# outra sobreposição interrompe o script (decisão do usuário, não do script).
CONFLITOS_RESOLVIDOS = {"configuracao_empresa"}

# Colunas com caminho de arquivo (relativo à pasta de dados: "uploads/...").
ARQUIVOS_INSTALADO = [("anexos_lancamento", "arquivo_path")]
ARQUIVOS_DEV = [("moldes", "arquivo_path"), ("empresa", "logo_path"), ("empresa", "certificado_path")]
# Tabela cujo registro é DESCARTADO quando o arquivo não existe (nas demais o
# registro fica e o arquivo só é listado como não encontrado).
DESCARTA_SEM_ARQUIVO = {"anexos_lancamento"}


@dataclass
class Relatorio:
    linhas: list[str] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)

    def __call__(self, texto: str = "") -> None:
        print(texto)
        self.linhas.append(texto)


def _tabelas(con: sqlite3.Connection, esquema: str = "main") -> set[str]:
    return {
        r[0]
        for r in con.execute(
            f"select name from {esquema}.sqlite_master where type='table' and name not like 'sqlite_%'"
        )
    }


def _colunas(con: sqlite3.Connection, tabela: str, esquema: str = "main") -> list[str]:
    return [r[1] for r in con.execute(f'pragma {esquema}.table_info("{tabela}")')]


def _contar(con: sqlite3.Connection, tabela: str, esquema: str = "main") -> int:
    return con.execute(f'select count(*) from {esquema}."{tabela}"').fetchone()[0]


def _uri_ro(caminho: Path) -> str:
    return f"{caminho.resolve().as_uri()}?mode=ro"


def _criar_banco(destino: Path) -> None:
    # Import tardio: services.db_migracoes puxa a config do backend.
    from services.db_migracoes import aplicar_migracoes

    aplicar_migracoes(f"sqlite:///{destino.resolve().as_posix()}")


def _copiar(con: sqlite3.Connection, esquema: str, tabela: str, rel: Relatorio) -> int:
    origem = set(_colunas(con, tabela, esquema))
    destino = _colunas(con, tabela)
    comuns = [c for c in destino if c in origem]
    sobrando = sorted(origem - set(destino))
    if sobrando:
        rel.erros.append(f"{tabela}: colunas da origem sem destino {sobrando}")
    lista = ", ".join(f'"{c}"' for c in comuns)
    con.execute(f'insert into main."{tabela}" ({lista}) select {lista} from {esquema}."{tabela}" order by rowid')
    return _contar(con, tabela)


def _destino_relativo(caminho: str, coluna: str) -> Path | None:
    """Caminho gravado na origem -> caminho relativo na pasta de dados nova.

    Relativo ("uploads/...", inclusive com "\\") fica igual; absoluto vira
    relativo pelo trecho a partir de "uploads/" (ex.: moldes gravados com o
    caminho completo do userData) ou, no certificado, "Certificados/<nome>".
    """
    p = Path(caminho.replace("\\", "/"))
    if not p.is_absolute():
        return None if ".." in p.parts else p
    partes = [x.lower() for x in p.parts]
    if "uploads" in partes:
        return Path(*p.parts[partes.index("uploads") :])
    if coluna == "certificado_path":
        return Path("Certificados") / p.name
    return None


def _copiar_arquivos(
    con: sqlite3.Connection, tabela: str, coluna: str, base: Path, saida: Path, rel: Relatorio
) -> tuple[int, list[str], int]:
    """Copia os arquivos referenciados para <saida> e grava no banco novo o
    caminho relativo normalizado. Retorna (copiados, não encontrados,
    registros descartados)."""
    copiados, faltando, descartados = 0, [], 0
    linhas = con.execute(
        f'select rowid, "{coluna}" from main."{tabela}" where "{coluna}" is not null and "{coluna}" <> "" order by rowid'
    ).fetchall()
    for rowid, caminho in linhas:
        relativo = _destino_relativo(caminho, coluna)
        if relativo is None:
            rel.erros.append(f"{tabela}.{coluna}: caminho fora da pasta de dados: {caminho}")
            continue
        absoluto = Path(caminho)
        candidatos = [absoluto] if absoluto.is_absolute() else []
        candidatos.append(base / relativo)
        src = next((c for c in candidatos if c.is_file()), None)
        if src is None:
            faltando.append(caminho)
            if tabela in DESCARTA_SEM_ARQUIVO:
                con.execute(f'delete from main."{tabela}" where rowid = ?', (rowid,))
                descartados += 1
            continue
        dst = saida / relativo
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(src, dst)
        con.execute(f'update main."{tabela}" set "{coluna}" = ? where rowid = ?', (relativo.as_posix(), rowid))
        copiados += 1
    return copiados, faltando, descartados


def _saldos_por_conta(con: sqlite3.Connection, esquema: str) -> dict[tuple, tuple]:
    """Saldo por conta e mês com a regra de GET /saldo-contas (saldo inicial
    do mês + recebidos - pagos no mês) e o pendente por conta (a receber -
    a pagar). Chave (conta, ano, mês) ou (conta, "pendente")."""
    saldos: dict[tuple, list] = {}
    for conta, mes, ano, valor in con.execute(
        f"select conta_bancaria_id, mes, ano, valor from {esquema}.saldo_inicial_conta"
    ):
        saldos.setdefault((conta, int(ano), int(mes)), [0.0, 0.0, 0.0])[0] += float(valor or 0)
    for conta, tipo, status, data_pag, valor in con.execute(
        f"select conta_bancaria_id, tipo, status, data_pagamento, valor from {esquema}.lancamentos "
        "where conta_bancaria_id is not null"
    ):
        if status == "PAGO" and data_pag:
            chave = (conta, int(str(data_pag)[:4]), int(str(data_pag)[5:7]))
        elif status != "PAGO":
            chave = (conta, "pendente")
        else:
            continue
        saldos.setdefault(chave, [0.0, 0.0, 0.0])[1 if tipo == "RECEBER" else 2] += float(valor or 0)
    return {k: (round(v[0] + v[1] - v[2], 2), round(v[1], 2), round(v[2], 2)) for k, v in saldos.items()}


def montar(instalado: Path, dev: Path, base_instalado: Path, base_dev: Path, saida: Path) -> int:
    for p in (instalado, dev):
        if not p.is_file():
            raise SystemExit(f"Banco não encontrado: {p}")
    if saida.exists():
        if not (saida / "smartcut.db").exists() and any(saida.iterdir()):
            raise SystemExit(f"A pasta de saída {saida} existe e não é uma saída deste script — escolha outra.")
        shutil.rmtree(saida)
    saida.mkdir(parents=True)
    banco = saida / "smartcut.db"
    rel = Relatorio()

    rel("MONTAGEM DO BANCO DE PRODUÇÃO — SmartCut 1.3.0")
    rel(f"instalado: {instalado}")
    rel(f"dev:       {dev}")
    rel(f"saída:     {banco}")
    rel()

    # 1. Banco novo com todas as migrações.
    _criar_banco(banco)

    con = sqlite3.connect(banco.resolve().as_uri(), uri=True)  # uri: ATTACH com mode=ro
    con.execute("pragma foreign_keys = OFF")
    con.execute(f"attach database '{_uri_ro(instalado)}' as inst")
    con.execute(f"attach database '{_uri_ro(dev)}' as dev")
    versao = con.execute("select version_num from alembic_version").fetchone()[0]
    rel(f"1. Estrutura: {len(_tabelas(con)) - 1} tabelas, alembic_version = {versao}")

    t_inst, t_dev, t_novo = _tabelas(con, "inst"), _tabelas(con, "dev"), _tabelas(con)
    for t in DO_INSTALADO:
        if t not in t_inst:
            raise SystemExit(f"Tabela {t} não existe no banco instalado.")
    for t in DO_DEV:
        if t not in t_dev:
            raise SystemExit(f"Tabela {t} não existe no banco de dev.")

    # 4. Conflitos: tabela do plano com dados nos dois bancos.
    plano = DO_INSTALADO + DO_DEV
    conflitos = [t for t in plano if t in t_inst and t in t_dev and _contar(con, t, "inst") and _contar(con, t, "dev")]
    nao_resolvidos = [t for t in conflitos if t not in CONFLITOS_RESOLVIDOS]
    rel(f"4. Conflitos (dados nos dois bancos): {conflitos or 'nenhum'}")
    if nao_resolvidos:
        con.close()
        raise SystemExit(
            f"Conflito sem regra definida em {nao_resolvidos}: decidir qual banco vale e acrescentar a regra ao script."
        )

    with con:
        contagens = []
        for esquema, tabelas in (("inst", DO_INSTALADO), ("dev", DO_DEV)):
            for t in tabelas:
                n_origem = _contar(con, t, esquema)
                n_destino = _copiar(con, esquema, t, rel)
                contagens.append((t, "instalado" if esquema == "inst" else "dev", n_origem, n_destino))

        # configuracao_empresa: linha do dev + valores reais do instalado.
        linha_inst = con.execute(
            f"select {', '.join(CONFIG_DO_INSTALADO)} from inst.configuracao_empresa order by rowid limit 1"
        ).fetchone()
        n_cfg = _contar(con, "configuracao_empresa")
        if linha_inst and n_cfg == 1:
            sets = ", ".join(f"{c} = ?" for c in CONFIG_DO_INSTALADO)
            con.execute(f"update main.configuracao_empresa set {sets}", linha_inst)
        elif linha_inst:
            rel.erros.append(f"configuracao_empresa: esperado 1 linha no dev, há {n_cfg}")

    rel()
    rel("2/3. Contagem por tabela (origem x destino):")
    rel(f"   {'tabela':28}{'origem':>11}{'qtd. origem':>13}{'qtd. destino':>14}")
    for t, origem, a, b in contagens:
        marca = "" if a == b else "   <-- DIFERENTE"
        if a != b:
            rel.erros.append(f"{t}: origem {a} x destino {b}")
        rel(f"   {t:28}{origem:>11}{a:>13}{b:>14}{marca}")
    cfg = con.execute(
        "select aliquota_simples, custo_etiqueta, comprimento_max_mesa_cm, alerta_economia_pct, "
        "tempo_maximo_oc_s, tolerancia_tecido_pct from configuracao_empresa"
    ).fetchone()
    rel(
        f"   configuracao_empresa mesclada: aliquota_simples={cfg[0]}, custo_etiqueta={cfg[1]} (instalado); "
        f"mesa={cfg[2]} cm, alerta={cfg[3]}%, tempo OC={cfg[4]} s, tolerância={cfg[5]}% (dev)"
    )

    # Tabelas com dados que ficaram de fora (para conferência).
    rel()
    rel("   Não copiadas (têm dados na origem):")
    for esquema, nome, tabelas in (("inst", "instalado", t_inst), ("dev", "dev", t_dev)):
        fora = [
            f"{t}({_contar(con, t, esquema)})"
            for t in sorted(tabelas)
            if t not in plano and t != "alembic_version" and _contar(con, t, esquema)
        ]
        rel(f"   - {nome}: {', '.join(fora) or 'nenhuma'}")
    sem_destino = sorted((t_inst | t_dev) - t_novo - {"alembic_version"})
    if sem_destino:
        rel(f"   - tabelas da origem inexistentes na head: {sem_destino}")

    # Arquivos referenciados.
    rel()
    rel("   Arquivos:")
    faltando_total: list[str] = []
    descartados_total = 0
    with con:
        for tabelas, base in ((ARQUIVOS_INSTALADO, base_instalado), (ARQUIVOS_DEV, base_dev)):
            for t, coluna in tabelas:
                ok, faltando, descartados = _copiar_arquivos(con, t, coluna, base, saida, rel)
                extra = f" — {descartados} registro(s) DESCARTADO(S): arquivo não existe" if descartados else ""
                rel(f"   - {t}.{coluna}: {ok} de {ok + len(faltando)} copiados (origem {base}){extra}")
                descartados_total += descartados
                if t not in DESCARTA_SEM_ARQUIVO:
                    faltando_total += [f"{t}: {f}" for f in faltando]
    rel(f"   Anexos descartados por arquivo inexistente: {descartados_total}")
    if faltando_total:
        rel(f"   ARQUIVOS NÃO ENCONTRADOS, registro mantido ({len(faltando_total)}):")
        for f in faltando_total:
            rel(f"     {f}")

    # 5. Saldos por conta: o descarte de anexos não pode mexer em lançamento.
    rel()
    saldos_origem = _saldos_por_conta(con, "inst")
    saldos_destino = _saldos_por_conta(con, "main")
    nomes = dict(con.execute("select id, nome from main.contas_bancarias"))
    rel("5. Saldos por conta (inicial + recebido - pago, por mês; pendente = a receber - a pagar):")
    rel(f"   {'conta':28}{'período':>10}{'origem':>14}{'destino':>14}")
    for chave in sorted(saldos_origem.keys() | saldos_destino.keys(), key=str):
        a, b = saldos_origem.get(chave), saldos_destino.get(chave)
        periodo = "pendente" if chave[1] == "pendente" else f"{chave[2]:02d}/{chave[1]}"
        nome = str(nomes.get(chave[0], chave[0]))[:27]
        marca = "" if a == b else "   <-- DIFERENTE"
        if a != b:
            rel.erros.append(f"saldo da conta {nome} ({periodo}): origem {a} x destino {b}")
        rel(f"   {nome:28}{periodo:>10}{a[0] if a else '-':>14}{b[0] if b else '-':>14}{marca}")

    con.execute("detach database inst")
    con.execute("detach database dev")

    # 6. Integridade.
    rel()
    integ = [r[0] for r in con.execute("pragma integrity_check")]
    fks = con.execute("pragma foreign_key_check").fetchall()
    rel(f"6. PRAGMA integrity_check: {', '.join(integ)}")
    rel(f"   PRAGMA foreign_key_check: {'sem erros' if not fks else f'{len(fks)} erro(s)'}")
    for linha in fks[:20]:
        rel(f"     {linha}")
    if integ != ["ok"]:
        rel.erros.append("integrity_check falhou")
    if fks:
        rel.erros.append(f"foreign_key_check: {len(fks)} erro(s)")
    con.close()

    rel()
    if rel.erros:
        rel("RESULTADO: COM ERROS")
        for e in rel.erros:
            rel(f"  - {e}")
    else:
        avisos = []
        if descartados_total:
            avisos.append(f"{descartados_total} anexo(s) descartado(s) por arquivo inexistente")
        if faltando_total:
            avisos.append(f"{len(faltando_total)} arquivo(s) não encontrado(s) com registro mantido")
        rel("RESULTADO: OK" + (f" ({'; '.join(avisos)})" if avisos else ""))
    (saida / "relatorio_montagem.txt").write_text("\n".join(rel.linhas) + "\n", encoding="utf-8")
    return 1 if rel.erros else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Monta o banco de produção da v1.3.0 (ver docstring).")
    ap.add_argument("--instalado", required=True, type=Path, help="cópia do smartcut.db instalado")
    ap.add_argument("--dev", required=True, type=Path, help="cópia do backend/smartcut.db")
    ap.add_argument(
        "--base-instalado", required=True, type=Path, help="pasta que contém uploads/financeiro do instalado"
    )
    ap.add_argument("--base-dev", required=True, type=Path, help="pasta que contém uploads/ do dev (backend/)")
    ap.add_argument("--saida", required=True, type=Path, help="pasta de saída (recriada a cada execução)")
    a = ap.parse_args(argv)
    return montar(a.instalado, a.dev, a.base_instalado, a.base_dev, a.saida)


if __name__ == "__main__":
    sys.exit(main())
