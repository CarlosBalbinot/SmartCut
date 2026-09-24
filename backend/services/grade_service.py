import re

from sqlalchemy.orm import Session

from models.configuracao_grade import ConfiguracaoGrade
from models.produto import ColunaGrade, LinhaGrade, Produto
from schemas.produto_schema import GradeItemCreate


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


def proximo_seq_grupo(db: Session, grupo_prefixo: str) -> int:
    """Próximo número sequencial para `grupo_prefixo`.

    Ainda não existe model de "produto filho" (SKU por combinação de
    grade) na base — conta a partir do código de Produto (pai) com esse
    prefixo, mesma lógica de produto_service._proximo_codigo. Revisar
    esta função quando o model de produto filho existir (próxima etapa).
    """
    prefixo = f"{grupo_prefixo}-"
    codigos = [row[0] for row in db.query(Produto.codigo).filter(Produto.codigo.like(f"{prefixo}%")).all()]
    max_val = 0
    for codigo in codigos:
        m = re.match(r"^\d+", codigo[len(prefixo) :])
        if m:
            max_val = max(max_val, int(m.group()))
    return max_val + 1
