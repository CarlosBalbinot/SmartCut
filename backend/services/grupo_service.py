import uuid

from sqlalchemy.orm import Session, selectinload

from models.grupo_molde import GrupoMolde
from models.molde import Molde
from schemas.molde_schema import GrupoImportCreate, GrupoMoldeUpdate


def listar(db: Session) -> list[dict]:
    grupos = (
        db.query(GrupoMolde)
        .options(selectinload(GrupoMolde.moldes))
        .order_by(GrupoMolde.criado_em.desc())
        .all()
    )
    return [_grupo_to_dict(g) for g in grupos]


def obter(db: Session, grupo_id: uuid.UUID) -> dict | None:
    grupo = (
        db.query(GrupoMolde)
        .options(selectinload(GrupoMolde.moldes))
        .filter(GrupoMolde.id == grupo_id)
        .first()
    )
    return _grupo_to_dict(grupo) if grupo else None


def importar_grupo(db: Session, payload: GrupoImportCreate) -> dict:
    """Cria o grupo e todos os moldes de todas as partes em uma transação."""
    grupo = GrupoMolde(nome=payload.nome_grupo)
    db.add(grupo)
    db.flush()  # gera grupo.id sem commit

    moldes_criados: list[Molde] = []
    for parte in payload.partes:
        for peca in parte.pecas:
            molde = Molde(
                nome=f"{parte.nome} {peca.tamanho}",
                arquivo_path=payload.arquivo_path,
                formato=payload.formato,
                peca=parte.nome,
                tamanho=peca.tamanho,
                sentido_fio=parte.sentido_fio,
                tipo_corte=parte.tipo_corte,
                rotacao_base=parte.rotacao_base,
                area_cm2=peca.area_cm2,
                geometria_json=peca.geometria_json,
                grupo_id=grupo.id,
            )
            db.add(molde)
            moldes_criados.append(molde)

    db.commit()
    db.refresh(grupo)
    for m in moldes_criados:
        db.refresh(m)

    grupo.moldes = moldes_criados
    return _grupo_to_dict(grupo)


def renomear(db: Session, grupo_id: uuid.UUID, dados: GrupoMoldeUpdate) -> dict | None:
    grupo = db.get(GrupoMolde, grupo_id)
    if not grupo:
        return None
    if dados.nome is not None:
        grupo.nome = dados.nome
    if dados.codigo is not None:
        grupo.codigo = dados.codigo
    db.commit()
    return obter(db, grupo_id)


def deletar(db: Session, grupo_id: uuid.UUID) -> bool:
    grupo = db.get(GrupoMolde, grupo_id)
    if not grupo:
        return False
    # moldes têm ON DELETE SET NULL → grupo_id vira NULL mas os moldes ficam
    db.delete(grupo)
    db.commit()
    return True


# ── helpers ──────────────────────────────────────────────────────────


def _grupo_to_dict(grupo: GrupoMolde) -> dict:
    return {
        "id": str(grupo.id),
        "nome": grupo.nome,
        "codigo": grupo.codigo,
        "criado_em": grupo.criado_em.isoformat(),
        "moldes": [_molde_to_dict(m) for m in grupo.moldes],
    }


def _molde_to_dict(m: Molde) -> dict:
    return {
        "id": str(m.id),
        "nome": m.nome,
        "arquivo_path": m.arquivo_path,
        "formato": m.formato,
        "peca": m.peca,
        "tamanho": m.tamanho,
        "sentido_fio": m.sentido_fio,
        "tipo_corte": m.tipo_corte,
        "rotacao_base": m.rotacao_base or 0,
        "area_cm2": float(m.area_cm2) if m.area_cm2 is not None else None,
        "geometria_json": m.geometria_json,
        "grupo_id": str(m.grupo_id) if m.grupo_id else None,
        "criado_em": m.criado_em.isoformat(),
    }
