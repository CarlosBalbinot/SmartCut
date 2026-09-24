import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from config import settings
from models.molde import Molde
from models.pedido import ItemPedido
from parsers.ads_parser import parse_ads
from parsers.dxf_parser import parse_dxf
from parsers.plt_parser import parse_plt
from schemas.molde_schema import BulkImportCreate, MoldeUpdate

PARSERS = {
    "DXF": parse_dxf,
    "PLT": parse_plt,
    "ADS": parse_ads,
}


def listar(db: Session) -> list[dict]:
    moldes = db.query(Molde).order_by(Molde.criado_em.desc()).all()
    return [_to_dict(m) for m in moldes]


def obter(db: Session, molde_id: uuid.UUID) -> dict | None:
    molde = db.get(Molde, molde_id)
    return _to_dict(molde) if molde else None


async def preview_arquivo(arquivo: UploadFile) -> dict:
    """Salva o arquivo e extrai as polylines sem persistir no banco.

    Retorna pecas ordenadas por area_cm2 crescente (menor tamanho primeiro).
    """
    extensao = Path(arquivo.filename).suffix.upper().lstrip(".")
    if extensao not in PARSERS:
        raise ValueError(f"Formato '{extensao}' não suportado. Use DXF, PLT ou ADS.")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    destino = upload_dir / f"{uuid.uuid4()}_{arquivo.filename}"

    conteudo = await arquivo.read()
    destino.write_bytes(conteudo)

    pecas = PARSERS[extensao](str(destino))
    pecas.sort(key=lambda p: p["area_cm2"])

    return {
        "arquivo_path": str(destino),
        "formato": extensao,
        "pecas": pecas,
    }


def importar_bulk(db: Session, payload: BulkImportCreate) -> list[dict]:
    """Salva no banco peças avulsas (sem grupo)."""
    moldes_criados: list[Molde] = []
    for peca in payload.pecas:
        molde = Molde(
            nome=peca.nome,
            arquivo_path=payload.arquivo_path,
            formato=payload.formato,
            peca=peca.peca,
            tamanho=peca.tamanho,
            sentido_fio=peca.sentido_fio,
            tipo_corte=peca.tipo_corte,
            rotacao_base=peca.rotacao_base,
            area_cm2=peca.area_cm2,
            geometria_json=peca.geometria_json,
        )
        db.add(molde)
        moldes_criados.append(molde)

    db.commit()
    for m in moldes_criados:
        db.refresh(m)

    return [_to_dict(m) for m in moldes_criados]


def atualizar(db: Session, molde_id: uuid.UUID, dados: MoldeUpdate) -> dict | None:
    molde = db.get(Molde, molde_id)
    if not molde:
        return None

    for campo, valor in dados.model_dump(exclude_none=True).items():
        setattr(molde, campo, valor)

    db.commit()
    db.refresh(molde)
    return _to_dict(molde)


def deletar(db: Session, molde_id: uuid.UUID) -> bool:
    molde = db.get(Molde, molde_id)
    if not molde:
        return False

    if molde.grupo_id is not None:
        # Vínculo real hoje é a nível de grupo: itens_pedido referencia o
        # grupo de moldes, não o molde individual (PedidoPeca/molde_id foi
        # removido na reestruturação e hoje é código morto).
        vinculado = db.query(ItemPedido).filter(ItemPedido.grupo_id == molde.grupo_id).first()
        if vinculado:
            raise ValueError(
                "Este molde não pode ser excluído pois está vinculado a um ou "
                "mais encaixes. Remova os encaixes primeiro."
            )

    db.delete(molde)
    db.commit()
    return True


def _to_dict(molde: Molde) -> dict:
    return {
        "id": str(molde.id),
        "nome": molde.nome,
        "arquivo_path": molde.arquivo_path,
        "formato": molde.formato,
        "peca": molde.peca,
        "tamanho": molde.tamanho,
        "sentido_fio": molde.sentido_fio,
        "tipo_corte": molde.tipo_corte,
        "rotacao_base": molde.rotacao_base or 0,
        "area_cm2": float(molde.area_cm2) if molde.area_cm2 is not None else None,
        "geometria_json": molde.geometria_json,
        "grupo_id": str(molde.grupo_id) if molde.grupo_id else None,
        "criado_em": molde.criado_em.isoformat(),
    }
