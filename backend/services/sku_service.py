import uuid

from sqlalchemy.orm import Session

from models.produto import Produto
from models.produto_sku import ProdutoSKU
from models.tabela_grade import ItemTabelaGrade
from services.grade_service import gerar_codigo_filho, proximo_seq_sku


def _obter_produto_pai_ou_erro(db: Session, produto_pai_id: uuid.UUID) -> Produto:
    produto = db.get(Produto, produto_pai_id)
    if not produto:
        raise ValueError("Produto pai não encontrado.")
    return produto


def _codigo_livre(db: Session, grupo_prefixo: str, cor: str | None, tam: str | None, desta_geracao: set[str]) -> str:
    """Código do SKU com o próximo {SEQ} da sequência do prefixo (atômica:
    duas gerações ao mesmo tempo nunca pegam o mesmo número). Se o código já
    existe — SKU antigo da regra anterior, que recomeçava a numeração, ou
    código digitado à mão —, pega o número seguinte."""
    while True:
        codigo = gerar_codigo_filho(db, grupo_prefixo, proximo_seq_sku(db, grupo_prefixo), cor, tam)
        if codigo in desta_geracao:
            continue
        with db.no_autoflush:
            existe = db.query(ProdutoSKU.id).filter(ProdutoSKU.codigo == codigo).first()
        if not existe:
            return codigo


def gerar_skus(db: Session, produto_pai_id: uuid.UUID, combinacoes: list[dict]) -> list[ProdutoSKU]:
    produto = _obter_produto_pai_ou_erro(db, produto_pai_id)
    grupo_prefixo = produto.grupo.prefixo

    criados = []
    for combo in combinacoes:
        linha_item_id = combo.get("linha_item_id")
        coluna_item_id = combo.get("coluna_item_id")

        existente = (
            db.query(ProdutoSKU)
            .filter(
                ProdutoSKU.produto_pai_id == produto_pai_id,
                ProdutoSKU.linha_item_id == linha_item_id,
                ProdutoSKU.coluna_item_id == coluna_item_id,
            )
            .first()
        )
        if existente:
            continue  # combinação já existe — não duplica

        linha_item = db.get(ItemTabelaGrade, linha_item_id) if linha_item_id else None
        coluna_item = db.get(ItemTabelaGrade, coluna_item_id) if coluna_item_id else None

        codigo = _codigo_livre(
            db,
            grupo_prefixo,
            linha_item.codigo_curto if linha_item else None,
            coluna_item.codigo_curto if coluna_item else None,
            {s.codigo for s in criados},
        )
        sku = ProdutoSKU(
            produto_pai_id=produto_pai_id,
            linha_item_id=linha_item_id,
            coluna_item_id=coluna_item_id,
            codigo=codigo,
        )
        db.add(sku)
        criados.append(sku)

    db.commit()
    for sku in criados:
        db.refresh(sku)
    return criados


def propagar_preco_pai(db: Session, produto_pai_id: uuid.UUID) -> dict:
    produto = _obter_produto_pai_ou_erro(db, produto_pai_id)
    skus = db.query(ProdutoSKU).filter(ProdutoSKU.produto_pai_id == produto_pai_id).all()

    atualizados = 0
    ignorados = 0
    for sku in skus:
        if sku.preco_manual:
            ignorados += 1
            continue
        sku.preco_venda = produto.preco_venda
        atualizados += 1
    db.commit()

    return {
        "atualizados": atualizados,
        "ignorados": ignorados,
        "mensagem": (
            f"{atualizados} produto(s) atualizado(s). {ignorados} produto(s) com preço manual não foram alterados."
        ),
    }


def _sku_tem_movimentacao(sku: ProdutoSKU) -> bool:
    # Nenhuma tabela de movimentação (ItemPedido — reaproveitado pela NF-e —
    # ou Encaixe) referencia ProdutoSKU hoje; elas só guardam produto_id no
    # nível do produto pai. Não há como checar movimentação por combinação
    # ainda, então nunca bloqueia. Revisar quando essas tabelas passarem a
    # referenciar produtos_sku.id (próxima etapa).
    return False


def remover_skus(db: Session, produto_pai_id: uuid.UUID, sku_ids: list[int]) -> dict:
    removidos = 0
    bloqueados = []
    for sku_id in sku_ids:
        sku = db.get(ProdutoSKU, sku_id)
        if not sku or sku.produto_pai_id != produto_pai_id:
            continue
        if _sku_tem_movimentacao(sku):
            bloqueados.append(sku.codigo)
            continue
        db.delete(sku)
        removidos += 1
    db.commit()
    return {"removidos": removidos, "bloqueados": bloqueados}


def sincronizar_skus(
    db: Session,
    produto_pai_id: uuid.UUID,
    novas_combinacoes: list[dict],
    remover_sku_ids: list[int],
) -> dict:
    """Aplica de uma vez as duas pontas da edição de grade: cria os SKUs
    das novas combinações e remove os SKUs desmarcados (respeitando o
    bloqueio por movimentação de `remover_skus`)."""
    criados = gerar_skus(db, produto_pai_id, novas_combinacoes)
    remocao = remover_skus(db, produto_pai_id, remover_sku_ids)
    return {
        "criados": len(criados),
        "removidos": remocao["removidos"],
        "bloqueados": remocao["bloqueados"],
    }
