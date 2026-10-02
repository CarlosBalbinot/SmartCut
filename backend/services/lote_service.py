import re
import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, case, func, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.util import identity_key

from models.tecido import LoteTecido
from schemas.tecido_schema import LoteCreate, LoteOut, LoteUpdate

_LIMITE_ALERTA_KG = 5.0
_MILESIMO = Decimal("0.001")


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


def _kg(peso_kg) -> Decimal:
    """Peso em Decimal com 3 casas, como a coluna (Numeric(10, 3))."""
    return Decimal(str(peso_kg)).quantize(_MILESIMO, rounding=ROUND_HALF_UP)


def _mover(db: Session, lote_id: uuid.UUID, peso, status) -> bool:
    """UPDATE do lote com o novo peso e status calculados NO BANCO, a partir
    do valor que está gravado na hora — nunca de um valor lido antes (F0,
    passo 2b). Duas OCs concluídas ao mesmo tempo no mesmo lote somam as
    duas baixas; com o cálculo em Python, a segunda gravava por cima da
    primeira (`peso lido − consumo`) e uma baixa sumia.

    Sem commit. Devolve False se o lote não existe. O objeto do lote que
    estiver na sessão é expirado, para a próxima leitura vir do banco."""
    mudou = db.execute(
        update(LoteTecido)
        .where(LoteTecido.id == lote_id)
        .values(peso_disponivel_kg=peso, status=status)
        .execution_options(synchronize_session=False)
    ).rowcount
    carregado = db.identity_map.get(identity_key(LoteTecido, lote_id))
    if carregado is not None:
        db.expire(carregado, ["peso_disponivel_kg", "status"])
    return mudou > 0


def debitar(db: Session, lote_id: uuid.UUID, peso_kg) -> bool:
    """Baixa `peso_kg` do lote e ajusta o status — SEM commit.

    O saldo para no zero (débito maior que o saldo zera o lote); lote
    intacto vira aberto e lote zerado vira esgotado. O commit é de quem
    chama: a conclusão da OC grava todos os consumos e a troca de status
    numa transação só, então o service do lote não pode commitar por conta
    própria.

        UPDATE lotes_tecido
           SET peso_disponivel_kg = CASE WHEN round(peso - :kg, 3) > 0
                                         THEN round(peso - :kg, 3) ELSE 0 END,
               status = CASE WHEN round(peso - :kg, 3) <= 0 THEN 'esgotado'
                             WHEN status = 'intacto' THEN 'aberto'
                             ELSE status END
         WHERE id = :id
    """
    peso = LoteTecido.peso_disponivel_kg
    restante = func.round(peso - _kg(peso_kg), 3)
    return _mover(
        db,
        lote_id,
        case((restante > 0, restante), else_=0),
        case(
            (restante <= 0, "esgotado"),
            (LoteTecido.status == "intacto", "aberto"),
            else_=LoteTecido.status,
        ),
    )


def creditar(db: Session, lote_id: uuid.UUID, peso_kg) -> bool:
    """Devolve `peso_kg` ao lote (estorno) e reativa um lote esgotado — SEM
    commit. Mesmo caminho do débito: a soma é feita no banco."""
    peso = LoteTecido.peso_disponivel_kg
    novo = func.round(peso + _kg(peso_kg), 3)
    # Só o esgotado volta a aberto: um lote arquivado continua arquivado.
    return _mover(
        db,
        lote_id,
        novo,
        case((and_(LoteTecido.status == "esgotado", novo > 0), "aberto"), else_=LoteTecido.status),
    )


def consumir(db: Session, lote_id: uuid.UUID, peso_kg: float) -> LoteOut | None:
    """Debita peso do lote e atualiza status para 'aberto' se estava intacto."""
    if not debitar(db, lote_id, peso_kg):
        return None
    db.commit()
    return LoteOut.model_validate(db.get(LoteTecido, lote_id))


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
