import re

from sqlalchemy.orm import Session

from models.configuracao_grade import ConfiguracaoGrade
from models.produto import ColunaGrade, LinhaGrade, Produto
from schemas.produto_schema import GradeItemCreate
from services import sequencia_service


def listar_linhas(db: Session, situacao: str | None = None) -> list[LinhaGrade]:
    q = db.query(LinhaGrade)
    if situacao:
        q = q.filter(LinhaGrade.situacao == situacao)
    return q.order_by(LinhaGrade.nome).all()


def criar_linha(db: Session, payload: GradeItemCreate) -> LinhaGrade:
    item = LinhaGrade(nome=payload.nome, situacao=payload.situacao)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def listar_colunas(db: Session, situacao: str | None = None) -> list[ColunaGrade]:
    q = db.query(ColunaGrade)
    if situacao:
        q = q.filter(ColunaGrade.situacao == situacao)
    return q.order_by(ColunaGrade.nome).all()


def criar_coluna(db: Session, payload: GradeItemCreate) -> ColunaGrade:
    item = ColunaGrade(nome=payload.nome, situacao=payload.situacao)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# ── Geração de código de produto filho (grade) ───────────────────────────


def obter_configuracao(db: Session) -> ConfiguracaoGrade:
    """Retorna o registro singleton (id=1) de ConfiguracaoGrade, criando-o
    com os valores padrão do model na primeira chamada."""
    config = db.get(ConfiguracaoGrade, 1)
    if not config:
        config = ConfiguracaoGrade(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def aplicar_mascara(
    mascara: str,
    separador: str,
    tamanho_seq: int,
    grupo_prefixo: str,
    seq: int,
    cor_codigo: str | None,
    tam_codigo: str | None,
) -> str:
    """Substitui as variáveis da máscara ({GRUPO}/{SEQ}/{COR}/{TAM}) e
    colapsa separadores duplicados/nas pontas deixados por variáveis
    vazias (ex.: "LG--M" → "LG-M")."""
    codigo = (
        mascara.replace("{GRUPO}", grupo_prefixo or "")
        .replace("{SEQ}", str(seq).zfill(tamanho_seq))
        .replace("{COR}", cor_codigo or "")
        .replace("{TAM}", tam_codigo or "")
    )
    if separador:
        codigo = re.sub(re.escape(separador) + r"{2,}", separador, codigo)
        codigo = codigo.strip(separador)
    return codigo


def gerar_codigo_filho(
    db: Session,
    grupo_prefixo: str,
    seq: int,
    cor_codigo: str | None,
    tam_codigo: str | None,
) -> str:
    config = obter_configuracao(db)
    return aplicar_mascara(
        config.mascara,
        config.separador,
        config.tamanho_seq,
        grupo_prefixo,
        seq,
        cor_codigo,
        tam_codigo,
    )


def seq_sku(grupo_prefixo: str) -> str:
    """Sequência do {SEQ} dos SKUs (F0, passo 1d), uma por prefixo de grupo."""
    return f"sku:{grupo_prefixo}"


def _ultimo_seq_sku(grupo_prefixo: str):
    """inicial(db) da sequência: a regra antiga — maior número dos códigos de
    Produto (pai) com esse prefixo. Os SKUs antigos podem ter usado números
    acima dele (a regra antiga recomeçava a cada geração); por isso quem gera
    pula os códigos que já existem (sku_service.gerar_skus)."""

    def inicial(db: Session) -> int:
        prefixo = f"{grupo_prefixo}-"
        max_val = 0
        for (codigo,) in db.query(Produto.codigo).filter(Produto.codigo.startswith(prefixo, autoescape=True)).all():
            m = re.match(r"^\d+", codigo[len(prefixo) :])
            if m:
                max_val = max(max_val, int(m.group()))
        return max_val

    return inicial


def proximo_seq_sku(db: Session, grupo_prefixo: str) -> int:
    """Próximo {SEQ} de SKU do prefixo — atômico, sem commit."""
    return sequencia_service.proximo(db, seq_sku(grupo_prefixo), _ultimo_seq_sku(grupo_prefixo))


def seq_do_codigo(db: Session, grupo_prefixo: str, codigo: str) -> int | None:
    """{SEQ} de um código de SKU lido com a máscara atual (ex.: código
    digitado à mão), ou None se o código não segue a máscara."""
    config = obter_configuracao(db)
    if "{SEQ}" not in config.mascara:
        return None
    padrao = re.escape(config.mascara)
    for var, regex in (
        ("{GRUPO}", re.escape(grupo_prefixo or "")),
        ("{SEQ}", rf"(?P<seq>\d{{{config.tamanho_seq},}}?)"),
        ("{COR}", ".*?"),
        ("{TAM}", ".*?"),
    ):
        padrao = padrao.replace(re.escape(var), regex, 1)
    m = re.fullmatch(padrao, codigo)
    return int(m.group("seq")) if m else None


def garantir_minimo_sku(db: Session, grupo_prefixo: str, codigo: str) -> None:
    """Código de SKU digitado à mão: a sequência do prefixo passa a entregar
    só números acima do {SEQ} dele (se a máscara atual consegue lê-lo)."""
    seq = seq_do_codigo(db, grupo_prefixo, codigo)
    if seq is not None:
        sequencia_service.garantir_minimo(db, seq_sku(grupo_prefixo), seq, _ultimo_seq_sku(grupo_prefixo))
