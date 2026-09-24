import re
import uuid

from sqlalchemy.orm import Session

from models.tecido import LoteTecido
from schemas.tecido_schema import LoteCreate, LoteOut, LoteUpdate

_LIMITE_ALERTA_KG = 5.0


def listar_por_cor(db: Session, cor_id: uuid.UUID) -> list[LoteOut]:
    lotes = (
        db.query(LoteTecido)
        .filter(LoteTecido.cor_id == cor_id, LoteTecido.status != "arquivado")
        .order_by(LoteTecido.data_compra)
        .all()
    )
    return [LoteOut.model_validate(lt) for lt in lotes]


def obter(db: Session, lote_id: uuid.UUID) -> LoteOut | None:
    lt = db.get(LoteTecido, lote_id)
    return LoteOut.model_validate(lt) if lt else None


def criar(db: Session, cor_id: uuid.UUID, payload: LoteCreate) -> LoteOut:
    lt = LoteTecido(
        cor_id=cor_id,
        codigo_lote=payload.codigo_lote,
        peso_inicial_kg=payload.peso_inicial_kg,
        peso_disponivel_kg=payload.peso_inicial_kg,
        valor_kg=payload.valor_kg,
        data_compra=payload.data_compra,
        status="intacto",
    )
    db.add(lt)
    db.commit()
    db.refresh(lt)
    return LoteOut.model_validate(lt)


def atualizar(db: Session, lote_id: uuid.UUID, payload: LoteUpdate) -> LoteOut | None:
    lt = db.get(LoteTecido, lote_id)
    if not lt:
        return None
    for campo, valor in payload.model_dump(exclude_none=True).items():
        setattr(lt, campo, valor)
    db.commit()
    db.refresh(lt)
    return LoteOut.model_validate(lt)


def arquivar(db: Session, lote_id: uuid.UUID) -> LoteOut | None:
    lt = db.get(LoteTecido, lote_id)
    if not lt:
        return None
    lt.status = "arquivado"
    db.commit()
    db.refresh(lt)
    return LoteOut.model_validate(lt)


def consumir(db: Session, lote_id: uuid.UUID, peso_kg: float) -> LoteOut | None:
    """Debita peso do lote e atualiza status para 'aberto' se estava intacto."""
    lt = db.get(LoteTecido, lote_id)
    if not lt:
        return None
    lt.peso_disponivel_kg = max(0.0, float(lt.peso_disponivel_kg) - peso_kg)
    if lt.status == "intacto":
        lt.status = "aberto"
    if lt.peso_disponivel_kg <= 0:
        lt.status = "esgotado"
    db.commit()
    db.refresh(lt)
    return LoteOut.model_validate(lt)


def verificar_alertas(db: Session) -> list[dict]:
    """Retorna lotes com peso_disponivel <= LIMITE_ALERTA_KG, exceto arquivados/esgotados."""
    from models.tecido import CorTecido
    from sqlalchemy.orm import selectinload

    lotes = (
        db.query(LoteTecido)
        .options(selectinload(LoteTecido.cor).selectinload(CorTecido.modelo))
        .filter(
            LoteTecido.peso_disponivel_kg <= _LIMITE_ALERTA_KG,
            LoteTecido.status.in_(["intacto", "aberto"]),
        )
        .all()
    )
    return [
        {
            "lote_id": str(lt.id),
            "codigo_lote": lt.codigo_lote,
            "peso_disponivel_kg": float(lt.peso_disponivel_kg),
            "cor_nome": lt.cor.nome_cor,
            "modelo_nome": lt.cor.modelo.nome,
        }
        for lt in lotes
    ]


def listar_historico(db: Session) -> list[LoteOut]:
    lotes = (
        db.query(LoteTecido)
        .filter(LoteTecido.status.in_(["arquivado", "esgotado"]))
        .order_by(LoteTecido.criado_em.desc())
        .all()
    )
    return [LoteOut.model_validate(lt) for lt in lotes]


def proximo_codigo(db: Session) -> str:
    """Sugere o próximo código de lote (ex: LT042)."""
    codigos = [row[0] for row in db.query(LoteTecido.codigo_lote).all()]
    max_num = 0
    for codigo in codigos:
        m = re.search(r"(\d+)$", codigo)
        if m:
            n = int(m.group(1))
            if n > max_num:
                max_num = n
    return f"LT{str(max_num + 1).zfill(3)}"
