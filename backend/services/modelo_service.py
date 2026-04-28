import uuid

from sqlalchemy.orm import Session, selectinload

from models.tecido import CorTecido, LoteTecido, ModeloTecido
from schemas.tecido_schema import ModeloComCoresOut, ModeloCreate, ModeloOut, ModeloUpdate


def _opts_completo():
    return [
        selectinload(ModeloTecido.cores).selectinload(CorTecido.lotes),
    ]


def listar(db: Session) -> list[ModeloComCoresOut]:
    modelos = (
        db.query(ModeloTecido)
        .options(*_opts_completo())
        .order_by(ModeloTecido.nome)
        .all()
    )
    return [_to_completo(m) for m in modelos]


def obter(db: Session, modelo_id: uuid.UUID) -> ModeloComCoresOut | None:
    modelo = (
        db.query(ModeloTecido)
        .options(*_opts_completo())
        .filter(ModeloTecido.id == modelo_id)
        .first()
    )
    return _to_completo(modelo) if modelo else None


def criar(db: Session, payload: ModeloCreate) -> ModeloOut:
    modelo = ModeloTecido(**payload.model_dump())
    db.add(modelo)
    db.commit()
    db.refresh(modelo)
    return ModeloOut.model_validate(modelo)


def atualizar(db: Session, modelo_id: uuid.UUID, payload: ModeloUpdate) -> ModeloOut | None:
    modelo = db.get(ModeloTecido, modelo_id)
    if not modelo:
        return None
    for campo, valor in payload.model_dump(exclude_none=True).items():
        setattr(modelo, campo, valor)
    db.commit()
    db.refresh(modelo)
    return ModeloOut.model_validate(modelo)


def deletar(db: Session, modelo_id: uuid.UUID) -> bool:
    modelo = db.get(ModeloTecido, modelo_id)
    if not modelo:
        return False
    db.delete(modelo)
    db.commit()
    return True


def _to_completo(modelo: ModeloTecido) -> ModeloComCoresOut:
    from schemas.tecido_schema import CorComLotesOut, LoteOut
    cores_out = []
    for cor in sorted(modelo.cores, key=lambda c: c.nome_cor):
        lotes_out = [
            LoteOut.model_validate(lt)
            for lt in sorted(cor.lotes, key=lambda l: l.criado_em)
            if lt.status not in ("arquivado",)
        ]
        cor_dict = {
            "id": cor.id,
            "modelo_id": cor.modelo_id,
            "nome_cor": cor.nome_cor,
            "largura_util_cm": float(cor.largura_util_cm),
            "gramatura_g_m2": float(cor.gramatura_g_m2),
            "encolhimento_pct": float(cor.encolhimento_pct),
            "criado_em": cor.criado_em,
            "lotes": lotes_out,
        }
        cores_out.append(CorComLotesOut(**cor_dict))

    return ModeloComCoresOut(
        id=modelo.id,
        nome=modelo.nome,
        tipo=modelo.tipo,
        max_camadas=modelo.max_camadas,
        criado_em=modelo.criado_em,
        cores=cores_out,
    )
