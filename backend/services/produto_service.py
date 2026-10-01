import uuid

from sqlalchemy.orm import Session, selectinload

from models.produto import GrupoProduto, Produto
from models.produto_sku import ProdutoSKU
from schemas.produto_schema import ProdutoCreate, ProdutoUpdate
from services import sequencia_service


def _opts():
    return [
        selectinload(Produto.grupo),
        selectinload(Produto.linha_grade),
        selectinload(Produto.coluna_grade),
        selectinload(Produto.skus),
    ]


def seq_produto(prefixo: str) -> str:
    """Sequência do código do produto (F0, passo 1d): uma por PREFIXO, não
    por grupo — o prefixo não é único entre grupos e o código (PREFIXO-NNN)
    é único no banco inteiro, então o prefixo é o espaço de numeração."""
    return f"produto:{prefixo}"


def _ultimo_numero(prefixo: str):
    """inicial(db): maior NNN já usado em códigos PREFIXO-NNN, de qualquer grupo."""

    def inicial(db: Session) -> int:
        inicio = f"{prefixo}-"
        max_val = 0
        for (codigo,) in db.query(Produto.codigo).filter(Produto.codigo.startswith(inicio, autoescape=True)).all():
            try:
                max_val = max(max_val, int(codigo[len(inicio) :]))
            except ValueError:
                pass
        return max_val

    return inicial


def _proximo_codigo(db: Session, grupo: GrupoProduto) -> str:
    n = sequencia_service.proximo(db, seq_produto(grupo.prefixo), _ultimo_numero(grupo.prefixo))
    return f"{grupo.prefixo}-{n:03d}"


def listar(
    db: Session,
    status: str | None = None,
    grupo_id: uuid.UUID | None = None,
    busca: str | None = None,
) -> list[Produto]:
    q = db.query(Produto).options(*_opts())
    if status:
        q = q.filter(Produto.status == status)
    if grupo_id:
        q = q.filter(Produto.grupo_id == grupo_id)
    if busca:
        termo = f"%{busca}%"
        q = q.filter((Produto.codigo.ilike(termo)) | (Produto.descricao.ilike(termo)))
    return q.order_by(Produto.codigo).all()


def listar_sellable(
    db: Session,
    status: str | None = None,
    grupo_id: uuid.UUID | None = None,
    busca: str | None = None,
) -> list[dict]:
    """Lista os itens "vendáveis": produtos autônomos (nunca usados para
    gerar grade) + cada SKU filho já gerado, como uma entrada própria.
    Produtos pai (is_pai=True) nunca aparecem — são apenas o molde da
    grade, não um item vendável em si."""
    q = db.query(Produto).options(*_opts()).filter(~Produto.skus.any())
    if grupo_id:
        q = q.filter(Produto.grupo_id == grupo_id)
    if status:
        q = q.filter(Produto.status == status)
    if busca:
        termo = f"%{busca}%"
        q = q.filter((Produto.codigo.ilike(termo)) | (Produto.descricao.ilike(termo)))
    autonomos = q.all()

    resultado = []
    for p in autonomos:
        resultado.append(
            {
                "id": str(p.id),
                "codigo": p.codigo,
                "descricao": p.descricao,
                "descricao_completa": p.descricao,
                "grupo_id": p.grupo_id,
                "unidade": p.unidade,
                "preco_venda": p.preco_venda,
                "status": p.status,
                "is_sku": False,
                "sku_id": None,
                "produto_pai_id": None,
                "codigo_pai": None,
                "linha_desc": None,
                "coluna_desc": None,
            }
        )

    skus_q = db.query(ProdutoSKU).options(
        selectinload(ProdutoSKU.produto_pai),
        selectinload(ProdutoSKU.linha_item),
        selectinload(ProdutoSKU.coluna_item),
    )
    if grupo_id:
        skus_q = skus_q.join(Produto, ProdutoSKU.produto_pai_id == Produto.id).filter(Produto.grupo_id == grupo_id)
    for s in skus_q.all():
        pai = s.produto_pai
        linha_desc = s.linha_item.descricao if s.linha_item else None
        coluna_desc = s.coluna_item.descricao if s.coluna_item else None
        descricao_completa = " ".join([pai.descricao, *(d for d in (linha_desc, coluna_desc) if d)])
        sku_status = "ativo" if s.situacao == "Ativo" else "inativo"

        if status and sku_status != status:
            continue
        if busca:
            termo = busca.lower()
            if termo not in s.codigo.lower() and termo not in descricao_completa.lower():
                continue

        resultado.append(
            {
                "id": f"sku-{s.id}",
                "codigo": s.codigo,
                "descricao": pai.descricao,
                "descricao_completa": descricao_completa,
                "grupo_id": pai.grupo_id,
                "unidade": pai.unidade,
                "preco_venda": s.preco_venda if s.preco_manual else pai.preco_venda,
                "status": sku_status,
                "is_sku": True,
                "sku_id": s.id,
                "produto_pai_id": pai.id,
                "codigo_pai": pai.codigo,
                "linha_desc": linha_desc,
                "coluna_desc": coluna_desc,
            }
        )

    resultado.sort(key=lambda r: r["codigo"])
    return resultado


def busca_pedido(db: Session, termo: str) -> list[dict]:
    """Busca para o Passo 1 do modal de adicionar item — mistura produtos
    pai (com grade de SKUs) e avulsos (sem SKUs) numa lista só, limitada
    a 20 resultados. SKUs filhos nunca aparecem aqui diretamente."""
    like = f"%{termo}%"
    produtos = (
        db.query(Produto)
        .options(
            selectinload(Produto.grupo),
            selectinload(Produto.skus),
            selectinload(Produto.linha_grade),
            selectinload(Produto.coluna_grade),
        )
        .filter(Produto.status == "ativo")
        .filter((Produto.codigo.ilike(like)) | (Produto.descricao.ilike(like)))
        .order_by(Produto.descricao)
        .limit(20)
        .all()
    )

    resultado = []
    for p in produtos:
        if p.is_pai:
            resultado.append(
                {
                    "tipo": "pai",
                    "id": str(p.id),
                    "codigo": p.codigo,
                    "descricao": p.descricao,
                    "grupo": p.grupo.nome if p.grupo else None,
                    "preco_venda": p.preco_venda,
                    "linha_grade_id": p.linha_grade_id,
                    "coluna_grade_id": p.coluna_grade_id,
                    "linha_grade_nome": p.linha_grade_nome,
                    "coluna_grade_nome": p.coluna_grade_nome,
                }
            )
        else:
            resultado.append(
                {
                    "tipo": "avulso",
                    "id": str(p.id),
                    "codigo": p.codigo,
                    "descricao": p.descricao,
                    "descricao_completa": p.descricao,
                    "grupo": p.grupo.nome if p.grupo else None,
                    "preco_venda": p.preco_venda,
                    "unidade": p.unidade,
                }
            )
    return resultado


def grade_pedido(db: Session, produto_pai_id: uuid.UUID) -> dict:
    """Grade de SKUs de um produto pai para o Passo 2 do modal de
    adicionar item, com o preço resolvido por SKU (ver regras no
    prompt: sku.preco_manual > pai.preco_venda > sem_preco — não existe
    preço de SKU por Tabela de Preço hoje, que continua sendo só por
    GrupoMolde/PrecoReferencia)."""
    produto = obter(db, produto_pai_id)
    if not produto:
        raise ValueError("Produto não encontrado.")
    if not produto.is_pai:
        raise ValueError("Produto não possui grade de SKUs.")

    def _eixo(tabela_grade) -> dict:
        if not tabela_grade:
            return {"id": None, "descricao": None, "itens": []}
        itens = [
            {"id": i.id, "codigo_curto": i.codigo_curto, "descricao": i.descricao, "ordem": i.ordem}
            for i in tabela_grade.itens
            if i.situacao == "Ativa"
        ]
        return {"id": tabela_grade.id, "descricao": tabela_grade.descricao, "itens": itens}

    skus_out = []
    for sku in sorted(produto.skus, key=lambda s: s.codigo):
        if sku.preco_manual and sku.preco_venda is not None:
            preco, origem = sku.preco_venda, "sku"
        elif produto.preco_venda and produto.preco_venda > 0:
            preco, origem = produto.preco_venda, "pai"
        else:
            preco, origem = None, "sem_preco"
        skus_out.append(
            {
                "id": sku.id,
                "codigo": sku.codigo,
                "linha_item_id": sku.linha_item_id,
                "coluna_item_id": sku.coluna_item_id,
                "preco_venda": preco,
                "preco_origem": origem,
                "situacao": sku.situacao,
            }
        )

    return {
        "produto": {
            "id": produto.id,
            "codigo": produto.codigo,
            "descricao": produto.descricao,
            "grupo": produto.grupo.nome if produto.grupo else None,
        },
        "linha_grade": _eixo(produto.linha_grade),
        "coluna_grade": _eixo(produto.coluna_grade),
        "skus": skus_out,
    }


def obter(db: Session, produto_id: uuid.UUID) -> Produto | None:
    return db.query(Produto).options(*_opts()).filter(Produto.id == produto_id).first()


def criar(db: Session, payload: ProdutoCreate) -> Produto:
    grupo = db.get(GrupoProduto, payload.grupo_id)
    if not grupo:
        raise ValueError("Grupo de produto não encontrado.")

    dados = payload.model_dump()
    produto = Produto(codigo=_proximo_codigo(db, grupo), **dados)
    db.add(produto)
    db.commit()
    db.refresh(produto)
    return obter(db, produto.id)


def atualizar(db: Session, produto_id: uuid.UUID, payload: ProdutoUpdate) -> Produto | None:
    produto = db.get(Produto, produto_id)
    if not produto:
        return None

    dados = payload.model_dump(exclude_unset=True)
    novo_grupo_id = dados.get("grupo_id")
    if novo_grupo_id and novo_grupo_id != produto.grupo_id:
        grupo = db.get(GrupoProduto, novo_grupo_id)
        if not grupo:
            raise ValueError("Grupo de produto não encontrado.")
        produto.codigo = _proximo_codigo(db, grupo)

    for campo, valor in dados.items():
        setattr(produto, campo, valor)

    db.commit()
    db.refresh(produto)
    return obter(db, produto.id)


def deletar(db: Session, produto_id: uuid.UUID) -> bool:
    produto = db.get(Produto, produto_id)
    if not produto:
        return False
    db.delete(produto)
    db.commit()
    return True
