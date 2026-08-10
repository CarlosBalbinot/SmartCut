import logging
import os
import shutil
import uuid
import xml.etree.ElementTree as ET
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models.financeiro import (
    AnexoLancamento,
    CompraFinanceira,
    ContaBancaria,
    Lancamento,
    MetaMensal,
    SaldoInicialConta,
    VendaFinanceira,
)
from schemas.financeiro_schema import (
    AnexoLancamentoOut,
    CompraComLancamentosOut,
    CompraCreate,
    CompraFinanceiraOut,
    CompraImportarXMLCreate,
    CompraUpdate,
    ConfirmarPagamento,
    ContaBancariaCreate,
    ContaBancariaOut,
    ContaBancariaUpdate,
    ImportacaoXMLResultOut,
    LancamentoCreate,
    LancamentoOut,
    LancamentoUpdate,
    MetaMensalCreate,
    MetaMensalOut,
    MetaMensalUpdate,
    NFeImportadaOut,
    ProjecaoMesOut,
    SaldoContaOut,
    VendaComLancamentosOut,
    VendaCreate,
    VendaFinanceiraOut,
    VendaImportarXMLCreate,
    VendaUpdate,
)

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])
logger = logging.getLogger(__name__)

_UPLOAD_DIR = "uploads/financeiro"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _add_meses(d: date, meses: int) -> date:
    """Avança d em `meses` meses, respeitando limites de dias por mês."""
    month = d.month - 1 + meses
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)


def _gerar_lancamentos(
    db: Session,
    *,
    tipo: str,
    descricao: str,
    valor_total: Decimal,
    parcelas: int,
    primeiro_vencimento: date,
    categoria_id: Optional[uuid.UUID],
    compra_id: Optional[uuid.UUID] = None,
    venda_id: Optional[uuid.UUID] = None,
) -> None:
    valor_parcela = (valor_total / parcelas).quantize(Decimal("0.01"))
    for i in range(parcelas):
        desc = descricao if parcelas == 1 else f"{descricao} ({i + 1}/{parcelas})"
        db.add(Lancamento(
            tipo=tipo,
            descricao=desc,
            valor=valor_parcela,
            valor_original=valor_parcela,
            data_vencimento=_add_meses(primeiro_vencimento, i),
            status="PENDENTE",
            parcela_numero=i + 1 if parcelas > 1 else None,
            parcela_total=parcelas if parcelas > 1 else None,
            categoria_id=categoria_id,
            compra_id=compra_id,
            venda_id=venda_id,
        ))


_NFE_NS = "{http://www.portalfiscal.inf.br/nfe}"


def _nfe_text(parent, tag: str) -> Optional[str]:
    if parent is None:
        return None
    node = parent.find(f"{_NFE_NS}{tag}")
    if node is None or not node.text:
        return None
    return node.text.strip()


def _find_text_any_ns(parent, tag: str) -> Optional[str]:
    """Busca `tag` dentro de `parent`, com e sem o namespace da NF-e."""
    if parent is None:
        return None
    node = parent.find(f"{_NFE_NS}{tag}")
    if node is None:
        node = parent.find(tag)
    if node is None or not node.text:
        return None
    return node.text.strip()


def _parse_nfe_xml(conteudo: bytes, party_tag: str = "emit") -> dict:
    """Faz o parse de um XML de NF-e (padrão SEFAZ) e extrai os dados da compra/venda.

    `party_tag` seleciona de qual parte da NF-e ler razão social/documento:
    "emit" (emitente → fornecedor, usado em compras) ou "dest" (destinatário
    → cliente, usado em vendas). O restante do XML (totais, datas, duplicatas)
    é lido da mesma forma em ambos os casos.
    """
    try:
        root = ET.fromstring(conteudo)
    except ET.ParseError as e:
        raise ValueError(f"XML inválido: {e}")

    inf_nfe = root.find(f".//{_NFE_NS}infNFe")
    if inf_nfe is None:
        raise ValueError("XML não é uma NF-e válida (infNFe não encontrado)")

    party = inf_nfe.find(f"{_NFE_NS}{party_tag}")
    ide = inf_nfe.find(f"{_NFE_NS}ide")
    total = inf_nfe.find(f"{_NFE_NS}total/{_NFE_NS}ICMSTot")

    fornecedor = _nfe_text(party, "xNome")
    cnpj_fornecedor = _nfe_text(party, "CNPJ") or _nfe_text(party, "CPF")
    numero_nf = _nfe_text(ide, "nNF")
    data_emissao_raw = _nfe_text(ide, "dEmi") or _nfe_text(ide, "dhEmi")
    valor_total_raw = _nfe_text(total, "vNF")

    if not fornecedor or not valor_total_raw or not data_emissao_raw:
        raise ValueError(
            "Não foi possível ler o nome da contraparte, valor total ou data de emissão do XML."
        )

    try:
        data_emissao = datetime.strptime(data_emissao_raw[:10], "%Y-%m-%d").date()
        valor_total = Decimal(valor_total_raw)
    except (ValueError, InvalidOperation):
        raise ValueError("Valores de data ou valor total inválidos no XML.")

    # Duplicatas (parcelas): tenta com o namespace da NF-e; se não achar, tenta sem namespace
    dups = root.findall(f".//{_NFE_NS}dup")
    if not dups:
        dups = root.findall(".//dup")
    logger.info("Importação NF-e: %d duplicata(s) encontrada(s) no XML", len(dups))

    parcelas = []
    for i, dup in enumerate(dups, start=1):
        d_venc = _find_text_any_ns(dup, "dVenc")
        v_dup = _find_text_any_ns(dup, "vDup")
        if not d_venc or not v_dup:
            continue
        try:
            parcelas.append({
                "numero": _find_text_any_ns(dup, "nDup") or f"{i:03d}",
                "vencimento": datetime.strptime(d_venc[:10], "%Y-%m-%d").date(),
                "valor": Decimal(v_dup),
            })
        except (ValueError, InvalidOperation):
            continue

    if not parcelas:
        parcelas.append({"numero": "001", "vencimento": None, "valor": valor_total})

    return {
        "fornecedor": fornecedor,
        "cnpj_fornecedor": cnpj_fornecedor,
        "valor_total": valor_total,
        "data_emissao": data_emissao,
        "numero_nf": numero_nf,
        "parcelas": parcelas,
    }


async def _processar_lote_xml(
    arquivos: list[UploadFile], party_tag: str
) -> list[ImportacaoXMLResultOut]:
    resultados = []
    for arquivo in arquivos:
        try:
            conteudo = await arquivo.read()
            dados = _parse_nfe_xml(conteudo, party_tag=party_tag)
            resultados.append(
                ImportacaoXMLResultOut(sucesso=True, dados=NFeImportadaOut(**dados), erro=None)
            )
        except ValueError as e:
            resultados.append(ImportacaoXMLResultOut(sucesso=False, dados=None, erro=str(e)))
        except Exception:
            resultados.append(
                ImportacaoXMLResultOut(
                    sucesso=False, dados=None,
                    erro=f"Falha ao processar '{arquivo.filename}'.",
                )
            )
    return resultados


# ── Contas Bancárias ──────────────────────────────────────────────────────────

@router.get("/contas-bancarias")
def listar_contas(db: Session = Depends(get_db)):
    rows = db.execute(
        select(ContaBancaria).order_by(ContaBancaria.nome)
    ).scalars().all()
    return {"data": [ContaBancariaOut.model_validate(r) for r in rows], "error": None}


@router.post("/contas-bancarias")
def criar_conta(payload: ContaBancariaCreate, db: Session = Depends(get_db)):
    conta = ContaBancaria(**payload.model_dump())
    db.add(conta)
    db.commit()
    db.refresh(conta)
    return {"data": ContaBancariaOut.model_validate(conta), "error": None}


@router.put("/contas-bancarias/{conta_id}")
def atualizar_conta(
    conta_id: uuid.UUID, payload: ContaBancariaUpdate, db: Session = Depends(get_db)
):
    conta = db.get(ContaBancaria, conta_id)
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(conta, field, val)
    db.commit()
    db.refresh(conta)
    return {"data": ContaBancariaOut.model_validate(conta), "error": None}


@router.delete("/contas-bancarias/{conta_id}")
def deletar_conta(conta_id: uuid.UUID, db: Session = Depends(get_db)):
    conta = db.get(ContaBancaria, conta_id)
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    db.delete(conta)
    db.commit()
    return {"data": None, "error": None}


# ── Saldo por Conta ───────────────────────────────────────────────────────────

@router.get("/saldo-contas")
def saldo_contas(mes: int, ano: int, db: Session = Depends(get_db)):
    contas = db.execute(
        select(ContaBancaria)
        .where(ContaBancaria.ativo == True)  # noqa: E712
        .order_by(ContaBancaria.nome)
    ).scalars().all()

    result = []
    for conta in contas:
        saldo_row = db.execute(
            select(SaldoInicialConta).where(
                SaldoInicialConta.conta_bancaria_id == conta.id,
                SaldoInicialConta.mes == mes,
                SaldoInicialConta.ano == ano,
            )
        ).scalars().first()
        saldo_inicial = saldo_row.valor if saldo_row else Decimal("0")

        entradas = db.execute(
            select(func.coalesce(func.sum(Lancamento.valor), 0)).where(
                Lancamento.conta_bancaria_id == conta.id,
                Lancamento.tipo == "RECEBER",
                Lancamento.status == "PAGO",
                extract("month", Lancamento.data_pagamento) == mes,
                extract("year", Lancamento.data_pagamento) == ano,
            )
        ).scalar()

        saidas = db.execute(
            select(func.coalesce(func.sum(Lancamento.valor), 0)).where(
                Lancamento.conta_bancaria_id == conta.id,
                Lancamento.tipo == "PAGAR",
                Lancamento.status == "PAGO",
                extract("month", Lancamento.data_pagamento) == mes,
                extract("year", Lancamento.data_pagamento) == ano,
            )
        ).scalar()

        total_entradas = Decimal(str(entradas or 0))
        total_saidas = Decimal(str(saidas or 0))
        result.append(SaldoContaOut(
            conta_id=conta.id,
            conta_nome=conta.nome,
            saldo_inicial=saldo_inicial,
            total_entradas=total_entradas,
            total_saidas=total_saidas,
            saldo_atual=saldo_inicial + total_entradas - total_saidas,
        ))

    return {"data": result, "error": None}


# ── Lançamentos ───────────────────────────────────────────────────────────────

@router.get("/lancamentos")
def listar_lancamentos(
    mes: Optional[int] = None,
    ano: Optional[int] = None,
    tipo: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = select(Lancamento).options(selectinload(Lancamento.anexos))
    if tipo:
        q = q.where(Lancamento.tipo == tipo)
    if mes is not None and ano is not None:
        q = q.where(
            extract("month", Lancamento.data_vencimento) == mes,
            extract("year", Lancamento.data_vencimento) == ano,
        )
    q = q.order_by(Lancamento.data_vencimento)
    rows = db.execute(q).scalars().all()
    return {"data": [LancamentoOut.model_validate(r) for r in rows], "error": None}


@router.post("/lancamentos")
def criar_lancamento(payload: LancamentoCreate, db: Session = Depends(get_db)):
    lancamento = Lancamento(**payload.model_dump(), valor_original=payload.valor)
    db.add(lancamento)
    db.commit()
    db.refresh(lancamento)
    return {"data": LancamentoOut.model_validate(lancamento), "error": None}


@router.put("/lancamentos/{lancamento_id}")
def atualizar_lancamento(
    lancamento_id: uuid.UUID, payload: LancamentoUpdate, db: Session = Depends(get_db)
):
    lancamento = db.get(Lancamento, lancamento_id)
    if not lancamento:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(lancamento, field, val)
    db.commit()
    db.refresh(lancamento)
    return {"data": LancamentoOut.model_validate(lancamento), "error": None}


@router.delete("/lancamentos/{lancamento_id}")
def deletar_lancamento(lancamento_id: uuid.UUID, db: Session = Depends(get_db)):
    lancamento = db.get(Lancamento, lancamento_id)
    if not lancamento:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    db.delete(lancamento)
    db.commit()
    return {"data": None, "error": None}


@router.post("/lancamentos/{lancamento_id}/confirmar-pagamento")
def confirmar_pagamento(
    lancamento_id: uuid.UUID,
    payload: ConfirmarPagamento,
    db: Session = Depends(get_db),
):
    lancamento = db.get(Lancamento, lancamento_id)
    if not lancamento:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    lancamento.status = "PAGO"
    lancamento.conta_bancaria_id = payload.conta_bancaria_id
    lancamento.data_pagamento = payload.data_pagamento
    db.commit()
    db.refresh(lancamento)
    return {"data": LancamentoOut.model_validate(lancamento), "error": None}


# ── Compras Financeiras ───────────────────────────────────────────────────────

@router.get("/compras")
def listar_compras(db: Session = Depends(get_db)):
    rows = db.execute(
        select(CompraFinanceira).order_by(CompraFinanceira.data_compra.desc())
    ).scalars().all()

    resultado = []
    for r in rows:
        total_parcelas = db.execute(
            select(func.count(Lancamento.id)).where(Lancamento.compra_id == r.id)
        ).scalar() or 0
        parcelas_pagas = db.execute(
            select(func.count(Lancamento.id)).where(
                Lancamento.compra_id == r.id,
                Lancamento.status == "PAGO",
            )
        ).scalar() or 0
        resultado.append(CompraFinanceiraOut(
            id=r.id,
            fornecedor=r.fornecedor,
            descricao=r.descricao,
            valor_total=r.valor_total,
            data_compra=r.data_compra,
            nf_pdf_path=r.nf_pdf_path,
            created_at=r.created_at,
            total_parcelas=total_parcelas,
            parcelas_pagas=parcelas_pagas,
        ))

    return {"data": resultado, "error": None}


@router.post("/compras")
def criar_compra(payload: CompraCreate, db: Session = Depends(get_db)):
    compra = CompraFinanceira(
        fornecedor=payload.fornecedor,
        descricao=payload.descricao,
        valor_total=payload.valor_total,
        data_compra=payload.data_compra,
    )
    db.add(compra)
    db.flush()

    _gerar_lancamentos(
        db,
        tipo="PAGAR",
        descricao=payload.descricao or payload.fornecedor,
        valor_total=payload.valor_total,
        parcelas=payload.parcelas,
        primeiro_vencimento=payload.primeiro_vencimento,
        categoria_id=payload.categoria_id,
        compra_id=compra.id,
    )
    db.commit()
    db.refresh(compra)
    return {"data": CompraFinanceiraOut.model_validate(compra), "error": None}


@router.post("/compras/importar-xml")
async def importar_xml_compra(arquivo: UploadFile = File(...)):
    conteudo = await arquivo.read()
    try:
        dados = _parse_nfe_xml(conteudo, party_tag="emit")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": NFeImportadaOut(**dados), "error": None}


@router.post("/compras/importar-lote")
async def importar_lote_compras(arquivos: list[UploadFile] = File(...)):
    resultados = await _processar_lote_xml(arquivos, party_tag="emit")
    return {"data": resultados, "error": None}


@router.post("/compras/importar")
def criar_compra_importada(payload: CompraImportarXMLCreate, db: Session = Depends(get_db)):
    if not payload.parcelas:
        raise HTTPException(status_code=400, detail="Informe ao menos uma parcela.")

    compra = CompraFinanceira(
        fornecedor=payload.fornecedor,
        descricao=payload.descricao,
        valor_total=payload.valor_total,
        data_compra=payload.data_compra,
    )
    db.add(compra)
    db.flush()

    total = len(payload.parcelas)
    descricao_base = payload.descricao or payload.fornecedor
    for i, parcela in enumerate(payload.parcelas, start=1):
        desc = descricao_base if total == 1 else f"{descricao_base} ({i}/{total})"
        db.add(Lancamento(
            tipo="PAGAR",
            descricao=desc,
            valor=parcela.valor,
            valor_original=parcela.valor,
            data_vencimento=parcela.vencimento,
            status="PENDENTE",
            parcela_numero=i if total > 1 else None,
            parcela_total=total if total > 1 else None,
            categoria_id=payload.categoria_id,
            compra_id=compra.id,
        ))

    db.commit()
    db.refresh(compra)
    return {"data": CompraFinanceiraOut.model_validate(compra), "error": None}


@router.get("/compras/{compra_id}")
def get_compra(compra_id: uuid.UUID, db: Session = Depends(get_db)):
    compra = db.execute(
        select(CompraFinanceira)
        .where(CompraFinanceira.id == compra_id)
        .options(
            selectinload(CompraFinanceira.lancamentos).selectinload(Lancamento.anexos)
        )
    ).scalars().first()
    if not compra:
        raise HTTPException(status_code=404, detail="Compra não encontrada")
    return {"data": CompraComLancamentosOut.model_validate(compra), "error": None}


@router.put("/compras/{compra_id}")
def atualizar_compra(
    compra_id: uuid.UUID, payload: CompraUpdate, db: Session = Depends(get_db)
):
    compra = db.execute(
        select(CompraFinanceira)
        .where(CompraFinanceira.id == compra_id)
        .options(selectinload(CompraFinanceira.lancamentos))
    ).scalars().first()
    if not compra:
        raise HTTPException(status_code=404, detail="Compra não encontrada")

    novo_valor = payload.valor_total
    valor_mudou = novo_valor is not None and novo_valor != compra.valor_total

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(compra, field, val)

    if valor_mudou and compra.lancamentos:
        total = compra.lancamentos[0].parcela_total or len(compra.lancamentos) or 1
        novo_por_parcela = (novo_valor / Decimal(total)).quantize(Decimal("0.01"))
        for lanc in compra.lancamentos:
            if lanc.status != "PAGO":
                lanc.valor = novo_por_parcela

    db.commit()
    db.refresh(compra)
    return {"data": CompraFinanceiraOut.model_validate(compra), "error": None}


@router.delete("/compras/{compra_id}")
def deletar_compra(compra_id: uuid.UUID, db: Session = Depends(get_db)):
    compra = db.execute(
        select(CompraFinanceira)
        .where(CompraFinanceira.id == compra_id)
        .options(
            selectinload(CompraFinanceira.lancamentos).selectinload(Lancamento.anexos)
        )
    ).scalars().first()
    if not compra:
        raise HTTPException(status_code=404, detail="Compra não encontrada")

    pagas = [l for l in compra.lancamentos if l.status == "PAGO"]
    if pagas:
        raise HTTPException(
            status_code=400,
            detail=f"Não é possível excluir: {len(pagas)} parcela(s) já foram pagas.",
        )

    for lanc in compra.lancamentos:
        for anexo in lanc.anexos:
            if os.path.exists(anexo.arquivo_path):
                try:
                    os.remove(anexo.arquivo_path)
                except OSError:
                    pass

    for lanc in compra.lancamentos:
        db.delete(lanc)

    db.delete(compra)
    db.commit()
    return {"data": None, "error": None}


# ── Vendas Financeiras ────────────────────────────────────────────────────────

@router.get("/vendas-financeiras")
def listar_vendas(db: Session = Depends(get_db)):
    rows = db.execute(
        select(VendaFinanceira).order_by(VendaFinanceira.data_venda.desc())
    ).scalars().all()

    resultado = []
    for r in rows:
        total_parcelas = db.execute(
            select(func.count(Lancamento.id)).where(Lancamento.venda_id == r.id)
        ).scalar() or 0
        parcelas_pagas = db.execute(
            select(func.count(Lancamento.id)).where(
                Lancamento.venda_id == r.id,
                Lancamento.status == "PAGO",
            )
        ).scalar() or 0
        resultado.append(VendaFinanceiraOut(
            id=r.id,
            cliente=r.cliente,
            descricao=r.descricao,
            valor_total=r.valor_total,
            data_venda=r.data_venda,
            nf_pdf_path=r.nf_pdf_path,
            created_at=r.created_at,
            total_parcelas=total_parcelas,
            parcelas_pagas=parcelas_pagas,
        ))

    return {"data": resultado, "error": None}


@router.post("/vendas-financeiras")
def criar_venda(payload: VendaCreate, db: Session = Depends(get_db)):
    venda = VendaFinanceira(
        cliente=payload.cliente,
        descricao=payload.descricao,
        valor_total=payload.valor_total,
        data_venda=payload.data_venda,
    )
    db.add(venda)
    db.flush()

    _gerar_lancamentos(
        db,
        tipo="RECEBER",
        descricao=payload.descricao or payload.cliente,
        valor_total=payload.valor_total,
        parcelas=payload.parcelas,
        primeiro_vencimento=payload.primeiro_vencimento,
        categoria_id=payload.categoria_id,
        venda_id=venda.id,
    )
    db.commit()
    db.refresh(venda)
    return {"data": VendaFinanceiraOut.model_validate(venda), "error": None}


@router.post("/vendas-financeiras/importar-xml")
async def importar_xml_venda(arquivo: UploadFile = File(...)):
    conteudo = await arquivo.read()
    try:
        dados = _parse_nfe_xml(conteudo, party_tag="dest")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": NFeImportadaOut(**dados), "error": None}


@router.post("/vendas-financeiras/importar-lote")
async def importar_lote_vendas(arquivos: list[UploadFile] = File(...)):
    resultados = await _processar_lote_xml(arquivos, party_tag="dest")
    return {"data": resultados, "error": None}


@router.post("/vendas-financeiras/importar")
def criar_venda_importada(payload: VendaImportarXMLCreate, db: Session = Depends(get_db)):
    if not payload.parcelas:
        raise HTTPException(status_code=400, detail="Informe ao menos uma parcela.")

    venda = VendaFinanceira(
        cliente=payload.cliente,
        descricao=payload.descricao,
        valor_total=payload.valor_total,
        data_venda=payload.data_venda,
    )
    db.add(venda)
    db.flush()

    total = len(payload.parcelas)
    descricao_base = payload.descricao or payload.cliente
    for i, parcela in enumerate(payload.parcelas, start=1):
        desc = descricao_base if total == 1 else f"{descricao_base} ({i}/{total})"
        db.add(Lancamento(
            tipo="RECEBER",
            descricao=desc,
            valor=parcela.valor,
            valor_original=parcela.valor,
            data_vencimento=parcela.vencimento,
            status="PENDENTE",
            parcela_numero=i if total > 1 else None,
            parcela_total=total if total > 1 else None,
            categoria_id=payload.categoria_id,
            venda_id=venda.id,
        ))

    db.commit()
    db.refresh(venda)
    return {"data": VendaFinanceiraOut.model_validate(venda), "error": None}


@router.get("/vendas-financeiras/{venda_id}")
def get_venda(venda_id: uuid.UUID, db: Session = Depends(get_db)):
    venda = db.execute(
        select(VendaFinanceira)
        .where(VendaFinanceira.id == venda_id)
        .options(
            selectinload(VendaFinanceira.lancamentos).selectinload(Lancamento.anexos)
        )
    ).scalars().first()
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada")
    return {"data": VendaComLancamentosOut.model_validate(venda), "error": None}


@router.put("/vendas-financeiras/{venda_id}")
def atualizar_venda(
    venda_id: uuid.UUID, payload: VendaUpdate, db: Session = Depends(get_db)
):
    venda = db.execute(
        select(VendaFinanceira)
        .where(VendaFinanceira.id == venda_id)
        .options(selectinload(VendaFinanceira.lancamentos))
    ).scalars().first()
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada")

    novo_valor = payload.valor_total
    valor_mudou = novo_valor is not None and novo_valor != venda.valor_total

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(venda, field, val)

    if valor_mudou and venda.lancamentos:
        total = venda.lancamentos[0].parcela_total or len(venda.lancamentos) or 1
        novo_por_parcela = (novo_valor / Decimal(total)).quantize(Decimal("0.01"))
        for lanc in venda.lancamentos:
            if lanc.status != "PAGO":
                lanc.valor = novo_por_parcela

    db.commit()
    db.refresh(venda)
    return {"data": VendaFinanceiraOut.model_validate(venda), "error": None}


@router.delete("/vendas-financeiras/{venda_id}")
def deletar_venda(venda_id: uuid.UUID, db: Session = Depends(get_db)):
    venda = db.execute(
        select(VendaFinanceira)
        .where(VendaFinanceira.id == venda_id)
        .options(
            selectinload(VendaFinanceira.lancamentos).selectinload(Lancamento.anexos)
        )
    ).scalars().first()
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada")

    pagas = [l for l in venda.lancamentos if l.status == "PAGO"]
    if pagas:
        raise HTTPException(
            status_code=400,
            detail=f"Não é possível excluir: {len(pagas)} parcela(s) já foram recebidas.",
        )

    for lanc in venda.lancamentos:
        for anexo in lanc.anexos:
            if os.path.exists(anexo.arquivo_path):
                try:
                    os.remove(anexo.arquivo_path)
                except OSError:
                    pass

    for lanc in venda.lancamentos:
        db.delete(lanc)

    db.delete(venda)
    db.commit()
    return {"data": None, "error": None}


# ── Upload de Anexos ──────────────────────────────────────────────────────────

@router.post("/lancamentos/{lancamento_id}/anexos")
async def upload_anexo(
    lancamento_id: uuid.UUID,
    arquivo: UploadFile = File(...),
    tipo: str = Form(...),
    db: Session = Depends(get_db),
):
    lancamento = db.get(Lancamento, lancamento_id)
    if not lancamento:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")

    pasta = os.path.join(_UPLOAD_DIR, str(lancamento_id))
    os.makedirs(pasta, exist_ok=True)

    nome_original = arquivo.filename or "arquivo.pdf"
    ext = os.path.splitext(nome_original)[1] or ".pdf"
    nome_arquivo = f"{uuid.uuid4()}{ext}"
    caminho = os.path.join(pasta, nome_arquivo)

    with open(caminho, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)

    anexo = AnexoLancamento(
        lancamento_id=lancamento_id,
        arquivo_path=caminho.replace("\\", "/"),
        tipo=tipo,
        nome_original=nome_original,
    )
    db.add(anexo)
    db.commit()
    db.refresh(anexo)
    return {"data": AnexoLancamentoOut.model_validate(anexo), "error": None}


@router.get("/lancamentos/{lancamento_id}/anexos")
def listar_anexos(lancamento_id: uuid.UUID, db: Session = Depends(get_db)):
    lancamento = db.get(Lancamento, lancamento_id)
    if not lancamento:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    rows = db.execute(
        select(AnexoLancamento)
        .where(AnexoLancamento.lancamento_id == lancamento_id)
        .order_by(AnexoLancamento.created_at)
    ).scalars().all()
    return {"data": [AnexoLancamentoOut.model_validate(r) for r in rows], "error": None}


@router.get("/anexos/{anexo_id}/download")
def download_anexo(anexo_id: uuid.UUID, db: Session = Depends(get_db)):
    anexo = db.get(AnexoLancamento, anexo_id)
    if not anexo:
        raise HTTPException(status_code=404, detail="Anexo não encontrado")
    if not os.path.exists(anexo.arquivo_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no servidor")
    return FileResponse(
        path=anexo.arquivo_path,
        filename=anexo.nome_original,
        media_type="application/octet-stream",
    )


@router.delete("/anexos/{anexo_id}")
def deletar_anexo(anexo_id: uuid.UUID, db: Session = Depends(get_db)):
    anexo = db.get(AnexoLancamento, anexo_id)
    if not anexo:
        raise HTTPException(status_code=404, detail="Anexo não encontrado")
    if os.path.exists(anexo.arquivo_path):
        try:
            os.remove(anexo.arquivo_path)
        except OSError:
            pass
    db.delete(anexo)
    db.commit()
    return {"data": None, "error": None}


# ── Projeção em Cascata ───────────────────────────────────────────────────────

@router.get("/projecao")
def projecao(
    mes_inicio: int,
    ano_inicio: int,
    meses: int = 3,
    db: Session = Depends(get_db),
):
    resultado = []
    saldo_cascata = Decimal("0")

    for i in range(meses):
        ref = _add_meses(date(ano_inicio, mes_inicio, 1), i)
        mes, ano = ref.month, ref.year

        if i == 0:
            total_saldo_inicial = db.execute(
                select(func.coalesce(func.sum(SaldoInicialConta.valor), 0)).where(
                    SaldoInicialConta.mes == mes,
                    SaldoInicialConta.ano == ano,
                )
            ).scalar()
            saldo_inicial = Decimal(str(total_saldo_inicial or 0))
        else:
            saldo_inicial = saldo_cascata

        entrar = db.execute(
            select(func.coalesce(func.sum(Lancamento.valor), 0)).where(
                Lancamento.tipo == "RECEBER",
                Lancamento.status != "PAGO",
                extract("month", Lancamento.data_vencimento) == mes,
                extract("year", Lancamento.data_vencimento) == ano,
            )
        ).scalar()

        sair = db.execute(
            select(func.coalesce(func.sum(Lancamento.valor), 0)).where(
                Lancamento.tipo == "PAGAR",
                Lancamento.status != "PAGO",
                extract("month", Lancamento.data_vencimento) == mes,
                extract("year", Lancamento.data_vencimento) == ano,
            )
        ).scalar()

        count = db.execute(
            select(func.count(Lancamento.id)).where(
                extract("month", Lancamento.data_vencimento) == mes,
                extract("year", Lancamento.data_vencimento) == ano,
            )
        ).scalar() or 0

        total_entrar = Decimal(str(entrar or 0))
        total_sair = Decimal(str(sair or 0))
        saldo_final = saldo_inicial + total_entrar - total_sair
        saldo_cascata = saldo_final

        resultado.append(ProjecaoMesOut(
            mes=mes,
            ano=ano,
            saldo_inicial=saldo_inicial,
            total_previsto_entrar=total_entrar,
            total_previsto_sair=total_sair,
            saldo_final_projetado=saldo_final,
            lancamentos_count=count,
        ))

    return {"data": resultado, "error": None}


# ── Metas ─────────────────────────────────────────────────────────────────────

@router.get("/metas")
def listar_metas(ano: Optional[int] = None, db: Session = Depends(get_db)):
    q = select(MetaMensal)
    if ano is not None:
        q = q.where(MetaMensal.ano == ano)
    q = q.order_by(MetaMensal.ano, MetaMensal.mes, MetaMensal.tipo)
    rows = db.execute(q).scalars().all()
    return {"data": [MetaMensalOut.model_validate(r) for r in rows], "error": None}


@router.post("/metas")
def criar_meta(payload: MetaMensalCreate, db: Session = Depends(get_db)):
    meta = MetaMensal(**payload.model_dump())
    db.add(meta)
    db.commit()
    db.refresh(meta)
    return {"data": MetaMensalOut.model_validate(meta), "error": None}


@router.put("/metas/{meta_id}")
def atualizar_meta(
    meta_id: uuid.UUID, payload: MetaMensalUpdate, db: Session = Depends(get_db)
):
    meta = db.get(MetaMensal, meta_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Meta não encontrada")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(meta, field, val)
    db.commit()
    db.refresh(meta)
    return {"data": MetaMensalOut.model_validate(meta), "error": None}
