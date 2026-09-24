import logging
import os
import re
import shutil
import uuid
import xml.etree.ElementTree as ET
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from middleware.permissions import require_permission
from models.financeiro import (
    AnexoLancamento,
    CompraFinanceira,
    ContaBancaria,
    Lancamento,
    MetaMensal,
    SaldoInicialConta,
    VendaFinanceira,
)
from models.venda import Empresa
from services.contabilidade_service import gerar_resumo_interno_pdf, montar_pacote_zip
from services.danfe_service import gerar_danfe_simplificada_pdf
from schemas.financeiro_schema import (
    AnexoLancamentoOut,
    CompraComLancamentosOut,
    CompraCreate,
    CompraFinanceiraOut,
    CompraImportarXMLCreate,
    CompraUpdate,
    ConfirmarPagamento,
    ContabilidadeGerarPacoteIn,
    ContabilidadeMesOut,
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
    SaldoInicialUpsert,
    TransferenciaCreate,
    TransferenciaOut,
    VendaComLancamentosOut,
    VendaCreate,
    VendaFinanceiraOut,
    VendaImportarXMLCreate,
    VendaUpdate,
)

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])
logger = logging.getLogger(__name__)

_UPLOAD_DIR = "uploads/financeiro"

# Este router cobre cinco telas distintas do Financeiro (Painel, Fluxo de
# Caixa, Compras, Vendas, Contabilidade); cada grupo de endpoints abaixo é
# protegido com o módulo correspondente àquela tela, não um único módulo
# para o arquivo inteiro. Ver relatório final para as dependências
# cruzadas entre módulos (ex.: anexos pertencem a financeiro_fluxo mas são
# usados também pelas telas de Compras/Vendas).
_PAINEL = "financeiro_painel"
_FLUXO = "financeiro_fluxo"
_COMPRAS = "financeiro_compras"
_VENDAS = "financeiro_vendas"
_CONTABIL = "financeiro_contabilidade"


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
        db.add(
            Lancamento(
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
            )
        )


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
        raise ValueError("Não foi possível ler o nome da contraparte, valor total ou data de emissão do XML.")

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
            parcelas.append(
                {
                    "numero": _find_text_any_ns(dup, "nDup") or f"{i:03d}",
                    "vencimento": datetime.strptime(d_venc[:10], "%Y-%m-%d").date(),
                    "valor": Decimal(v_dup),
                }
            )
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


def _find_any_ns(parent, tag: str):
    """Busca um elemento filho `tag` em `parent`, com e sem o namespace da NF-e."""
    if parent is None:
        return None
    node = parent.find(f"{_NFE_NS}{tag}")
    if node is None:
        node = parent.find(tag)
    return node


def _cnpj_cpf_fmt(doc: Optional[str]) -> Optional[str]:
    if not doc:
        return None
    d = re.sub(r"\D", "", doc)
    if len(d) == 14:
        return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"
    if len(d) == 11:
        return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"
    return doc


def _parse_party_danfe(party, ender) -> dict:
    nome = _find_text_any_ns(party, "xNome")
    documento = _find_text_any_ns(party, "CNPJ") or _find_text_any_ns(party, "CPF")
    ie = _find_text_any_ns(party, "IE")
    lgr = _find_text_any_ns(ender, "xLgr")
    nro = _find_text_any_ns(ender, "nro")
    bairro = _find_text_any_ns(ender, "xBairro")
    mun = _find_text_any_ns(ender, "xMun")
    uf = _find_text_any_ns(ender, "UF")
    cep = _find_text_any_ns(ender, "CEP")

    rua = " ".join(filter(None, [lgr, f"nº {nro}" if nro else None]))
    endereco = ", ".join(filter(None, [rua or None, bairro]))
    cidade_uf = "/".join(filter(None, [mun, uf])) if (mun or uf) else None

    return {
        "nome": nome,
        "documento": _cnpj_cpf_fmt(documento),
        "ie": ie,
        "endereco": endereco or None,
        "logradouro": lgr,
        "numero": nro,
        "bairro": bairro,
        "municipio": mun,
        "uf": uf,
        "cidade_uf": cidade_uf,
        "cep": cep,
    }


def _parse_nfe_danfe(conteudo: bytes) -> dict:
    """Faz o parse de um XML de NF-e (padrão SEFAZ) para gerar a DANFE Simplificada."""
    try:
        root = ET.fromstring(conteudo)
    except ET.ParseError as e:
        raise ValueError(f"XML inválido: {e}")

    inf_nfe = root.find(f".//{_NFE_NS}infNFe")
    if inf_nfe is None:
        inf_nfe = root.find(".//infNFe")
    if inf_nfe is None:
        raise ValueError("XML não é uma NF-e válida (infNFe não encontrado)")

    emit = _find_any_ns(inf_nfe, "emit")
    dest = _find_any_ns(inf_nfe, "dest")
    ide = _find_any_ns(inf_nfe, "ide")
    total = _find_any_ns(_find_any_ns(inf_nfe, "total"), "ICMSTot")

    emitente = _parse_party_danfe(emit, _find_any_ns(emit, "enderEmit"))
    destinatario = _parse_party_danfe(dest, _find_any_ns(dest, "enderDest"))

    if not emitente["nome"]:
        raise ValueError("Não foi possível ler os dados do emitente no XML.")

    numero_nf = _find_text_any_ns(ide, "nNF")
    serie = _find_text_any_ns(ide, "serie")
    natureza_operacao = _find_text_any_ns(ide, "natOp")
    data_emissao_raw = _find_text_any_ns(ide, "dEmi") or _find_text_any_ns(ide, "dhEmi")

    data_emissao = None
    if data_emissao_raw:
        try:
            data_emissao = datetime.strptime(data_emissao_raw[:10], "%Y-%m-%d").date()
        except ValueError:
            data_emissao = None

    def _dec(v: Optional[str]) -> Optional[Decimal]:
        try:
            return Decimal(v) if v else None
        except InvalidOperation:
            return None

    valor_total = _dec(_find_text_any_ns(total, "vNF"))
    valor_produtos = _dec(_find_text_any_ns(total, "vProd"))
    valor_frete = _dec(_find_text_any_ns(total, "vFrete"))

    chave = None
    id_attr = inf_nfe.get("Id")
    if id_attr:
        chave = id_attr.replace("NFe", "").strip()
    if not chave:
        chave_node = root.find(f".//{_NFE_NS}chNFe")
        if chave_node is None:
            chave_node = root.find(".//chNFe")
        if chave_node is not None and chave_node.text:
            chave = chave_node.text.strip()
    if not chave:
        raise ValueError("Não foi possível localizar a chave de acesso da NF-e no XML.")

    tipo_operacao = _find_text_any_ns(ide, "tpNF")

    # O protocolo de autorização fica em nfeProc/protNFe/infProt, fora da NFe
    # principal — por isso a busca parte de `root` (a tag raiz do documento,
    # nfeProc quando presente) em vez de `inf_nfe`.
    protocolo = None
    for tag in [f"{_NFE_NS}nProt", "nProt"]:
        el = root.find(f".//{tag}")
        if el is not None and el.text:
            protocolo = el.text.strip()
            break

    dh_recbto = None
    for tag in [f"{_NFE_NS}dhRecbto", "dhRecbto"]:
        el = root.find(f".//{tag}")
        if el is not None and el.text:
            dh_recbto = el.text.strip()
            break

    logger.warning("[DANFE] nProt encontrado: %s", protocolo)
    logger.warning("[DANFE] dhRecbto encontrado: %s", dh_recbto)

    data_protocolo = None
    if dh_recbto:
        try:
            data_protocolo = datetime.fromisoformat(dh_recbto)
        except ValueError:
            data_protocolo = None

    return {
        "emitente": emitente,
        "destinatario": destinatario,
        "numero_nf": numero_nf,
        "serie": serie,
        "data_emissao": data_emissao,
        "natureza_operacao": natureza_operacao,
        "valor_total": valor_total,
        "valor_produtos": valor_produtos,
        "valor_frete": valor_frete,
        "chave_acesso": chave,
        "tipo_operacao": tipo_operacao,
        "protocolo": protocolo,
        "data_protocolo": data_protocolo,
    }


async def _processar_lote_xml(arquivos: list[UploadFile], party_tag: str) -> list[ImportacaoXMLResultOut]:
    resultados = []
    for arquivo in arquivos:
        try:
            conteudo = await arquivo.read()
            dados = _parse_nfe_xml(conteudo, party_tag=party_tag)
            resultados.append(ImportacaoXMLResultOut(sucesso=True, dados=NFeImportadaOut(**dados), erro=None))
        except ValueError as e:
            resultados.append(ImportacaoXMLResultOut(sucesso=False, dados=None, erro=str(e)))
        except Exception:
            resultados.append(
                ImportacaoXMLResultOut(
                    sucesso=False,
                    dados=None,
                    erro=f"Falha ao processar '{arquivo.filename}'.",
                )
            )
    return resultados


# ── Contas Bancárias ──────────────────────────────────────────────────────────


@router.get("/contas-bancarias", dependencies=[Depends(require_permission(_FLUXO, "ver"))])
def listar_contas(db: Session = Depends(get_db)):
    rows = db.execute(select(ContaBancaria).order_by(ContaBancaria.nome)).scalars().all()
    return {"data": [ContaBancariaOut.model_validate(r) for r in rows], "error": None}


@router.post("/contas-bancarias", dependencies=[Depends(require_permission(_FLUXO, "criar"))])
def criar_conta(payload: ContaBancariaCreate, db: Session = Depends(get_db)):
    conta = ContaBancaria(**payload.model_dump())
    db.add(conta)
    db.commit()
    db.refresh(conta)
    return {"data": ContaBancariaOut.model_validate(conta), "error": None}


@router.put(
    "/contas-bancarias/{conta_id}",
    dependencies=[Depends(require_permission(_FLUXO, "editar"))],
)
def atualizar_conta(conta_id: uuid.UUID, payload: ContaBancariaUpdate, db: Session = Depends(get_db)):
    conta = db.get(ContaBancaria, conta_id)
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(conta, field, val)
    db.commit()
    db.refresh(conta)
    return {"data": ContaBancariaOut.model_validate(conta), "error": None}


@router.delete(
    "/contas-bancarias/{conta_id}",
    dependencies=[Depends(require_permission(_FLUXO, "excluir"))],
)
def deletar_conta(conta_id: uuid.UUID, db: Session = Depends(get_db)):
    conta = db.get(ContaBancaria, conta_id)
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    db.delete(conta)
    db.commit()
    return {"data": None, "error": None}


# ── Saldo por Conta ───────────────────────────────────────────────────────────


@router.get("/saldo-contas", dependencies=[Depends(require_permission(_FLUXO, "ver"))])
def saldo_contas(mes: int, ano: int, db: Session = Depends(get_db)):
    contas = (
        db.execute(
            select(ContaBancaria)
            .where(ContaBancaria.ativo == True)  # noqa: E712
            .order_by(ContaBancaria.nome)
        )
        .scalars()
        .all()
    )

    result = []
    for conta in contas:
        saldo_row = (
            db.execute(
                select(SaldoInicialConta).where(
                    SaldoInicialConta.conta_bancaria_id == conta.id,
                    SaldoInicialConta.mes == mes,
                    SaldoInicialConta.ano == ano,
                )
            )
            .scalars()
            .first()
        )
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
        result.append(
            SaldoContaOut(
                conta_id=conta.id,
                conta_nome=conta.nome,
                conta_tipo=conta.tipo,
                saldo_inicial=saldo_inicial,
                total_entradas=total_entradas,
                total_saidas=total_saidas,
                saldo_atual=saldo_inicial + total_entradas - total_saidas,
            )
        )

    return {"data": result, "error": None}


@router.post("/saldo-inicial", dependencies=[Depends(require_permission(_FLUXO, "editar"))])
def upsert_saldo_inicial(payload: SaldoInicialUpsert, db: Session = Depends(get_db)):
    conta = db.get(ContaBancaria, payload.conta_bancaria_id)
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    saldo = (
        db.execute(
            select(SaldoInicialConta).where(
                SaldoInicialConta.conta_bancaria_id == payload.conta_bancaria_id,
                SaldoInicialConta.mes == payload.mes,
                SaldoInicialConta.ano == payload.ano,
            )
        )
        .scalars()
        .first()
    )

    if saldo:
        saldo.valor = payload.valor
    else:
        saldo = SaldoInicialConta(
            conta_bancaria_id=payload.conta_bancaria_id,
            mes=payload.mes,
            ano=payload.ano,
            valor=payload.valor,
        )
        db.add(saldo)

    db.commit()
    db.refresh(saldo)
    return {
        "data": {
            "conta_bancaria_id": saldo.conta_bancaria_id,
            "mes": saldo.mes,
            "ano": saldo.ano,
            "valor": saldo.valor,
        },
        "error": None,
    }


# ── Transferências entre contas ───────────────────────────────────────────────


@router.post("/transferencias", dependencies=[Depends(require_permission(_FLUXO, "criar"))])
def criar_transferencia(payload: TransferenciaCreate, db: Session = Depends(get_db)):
    conta_origem = db.get(ContaBancaria, payload.conta_origem_id)
    conta_destino = db.get(ContaBancaria, payload.conta_destino_id)
    if not conta_origem or not conta_destino:
        raise HTTPException(status_code=404, detail="Conta de origem ou destino não encontrada")
    if payload.conta_origem_id == payload.conta_destino_id:
        raise HTTPException(status_code=400, detail="Conta de origem e destino devem ser diferentes")

    transferencia_id = uuid.uuid4()
    sufixo = f" — {payload.descricao}" if payload.descricao else ""

    saida = Lancamento(
        tipo="PAGAR",
        status="PAGO",
        descricao=f"Transferência para {conta_destino.nome}{sufixo}",
        valor=payload.valor,
        valor_original=payload.valor,
        data_vencimento=payload.data,
        data_pagamento=payload.data,
        conta_bancaria_id=payload.conta_origem_id,
        transferencia_id=transferencia_id,
    )
    entrada = Lancamento(
        tipo="RECEBER",
        status="PAGO",
        descricao=f"Transferência de {conta_origem.nome}{sufixo}",
        valor=payload.valor,
        valor_original=payload.valor,
        data_vencimento=payload.data,
        data_pagamento=payload.data,
        conta_bancaria_id=payload.conta_destino_id,
        transferencia_id=transferencia_id,
    )
    db.add(saida)
    db.add(entrada)
    db.commit()

    return {
        "data": TransferenciaOut(
            transferencia_id=transferencia_id,
            data=payload.data,
            conta_origem_id=conta_origem.id,
            conta_origem_nome=conta_origem.nome,
            conta_destino_id=conta_destino.id,
            conta_destino_nome=conta_destino.nome,
            valor=payload.valor,
            descricao=payload.descricao,
        ),
        "error": None,
    }


@router.get("/transferencias", dependencies=[Depends(require_permission(_FLUXO, "ver"))])
def listar_transferencias(mes: int, ano: int, db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(Lancamento)
            .where(
                Lancamento.transferencia_id.isnot(None),
                extract("month", Lancamento.data_vencimento) == mes,
                extract("year", Lancamento.data_vencimento) == ano,
            )
            .options(selectinload(Lancamento.conta_bancaria))
            .order_by(Lancamento.data_vencimento)
        )
        .scalars()
        .all()
    )

    grupos: dict[uuid.UUID, dict] = {}
    for lancamento in rows:
        grupos.setdefault(lancamento.transferencia_id, {})[lancamento.tipo] = lancamento

    resultado = []
    for transferencia_id, pernas in grupos.items():
        saida = pernas.get("PAGAR")
        entrada = pernas.get("RECEBER")
        if not saida or not entrada:
            continue
        descricao = None
        if " — " in saida.descricao:
            descricao = saida.descricao.split(" — ", 1)[1]
        resultado.append(
            TransferenciaOut(
                transferencia_id=transferencia_id,
                data=saida.data_vencimento,
                conta_origem_id=saida.conta_bancaria_id,
                conta_origem_nome=saida.conta_bancaria.nome if saida.conta_bancaria else "",
                conta_destino_id=entrada.conta_bancaria_id,
                conta_destino_nome=entrada.conta_bancaria.nome if entrada.conta_bancaria else "",
                valor=saida.valor,
                descricao=descricao,
            )
        )

    resultado.sort(key=lambda t: t.data)
    return {"data": resultado, "error": None}


# ── Lançamentos ───────────────────────────────────────────────────────────────


@router.get("/lancamentos", dependencies=[Depends(require_permission(_FLUXO, "ver"))])
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


@router.post("/lancamentos", dependencies=[Depends(require_permission(_FLUXO, "criar"))])
def criar_lancamento(payload: LancamentoCreate, db: Session = Depends(get_db)):
    lancamento = Lancamento(**payload.model_dump(), valor_original=payload.valor)
    db.add(lancamento)
    db.commit()
    db.refresh(lancamento)
    return {"data": LancamentoOut.model_validate(lancamento), "error": None}


@router.put(
    "/lancamentos/{lancamento_id}",
    dependencies=[Depends(require_permission(_FLUXO, "editar"))],
)
def atualizar_lancamento(lancamento_id: uuid.UUID, payload: LancamentoUpdate, db: Session = Depends(get_db)):
    lancamento = db.get(Lancamento, lancamento_id)
    if not lancamento:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(lancamento, field, val)
    db.commit()
    db.refresh(lancamento)
    return {"data": LancamentoOut.model_validate(lancamento), "error": None}


@router.delete(
    "/lancamentos/{lancamento_id}",
    dependencies=[Depends(require_permission(_FLUXO, "excluir"))],
)
def deletar_lancamento(lancamento_id: uuid.UUID, db: Session = Depends(get_db)):
    lancamento = db.get(Lancamento, lancamento_id)
    if not lancamento:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    db.delete(lancamento)
    db.commit()
    return {"data": None, "error": None}


@router.post(
    "/lancamentos/{lancamento_id}/confirmar-pagamento",
    dependencies=[Depends(require_permission(_FLUXO, "confirmar"))],
)
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


@router.get("/compras", dependencies=[Depends(require_permission(_COMPRAS, "ver"))])
def listar_compras(db: Session = Depends(get_db)):
    rows = db.execute(select(CompraFinanceira).order_by(CompraFinanceira.data_compra.desc())).scalars().all()

    resultado = []
    for r in rows:
        total_parcelas = db.execute(select(func.count(Lancamento.id)).where(Lancamento.compra_id == r.id)).scalar() or 0
        parcelas_pagas = (
            db.execute(
                select(func.count(Lancamento.id)).where(
                    Lancamento.compra_id == r.id,
                    Lancamento.status == "PAGO",
                )
            ).scalar()
            or 0
        )
        resultado.append(
            CompraFinanceiraOut(
                id=r.id,
                fornecedor=r.fornecedor,
                descricao=r.descricao,
                valor_total=r.valor_total,
                data_compra=r.data_compra,
                nf_pdf_path=r.nf_pdf_path,
                created_at=r.created_at,
                total_parcelas=total_parcelas,
                parcelas_pagas=parcelas_pagas,
            )
        )

    return {"data": resultado, "error": None}


@router.post("/compras", dependencies=[Depends(require_permission(_COMPRAS, "criar"))])
def criar_compra(payload: CompraCreate, db: Session = Depends(get_db)):
    compra = CompraFinanceira(
        fornecedor=payload.fornecedor,
        descricao=payload.descricao,
        valor_total=payload.valor_total,
        data_compra=payload.data_compra,
        numero_nf=payload.numero_nf,
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


@router.post(
    "/compras/importar-xml",
    dependencies=[Depends(require_permission(_COMPRAS, "criar"))],
)
async def importar_xml_compra(arquivo: UploadFile = File(...)):
    conteudo = await arquivo.read()
    try:
        dados = _parse_nfe_xml(conteudo, party_tag="emit")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": NFeImportadaOut(**dados), "error": None}


@router.post(
    "/compras/importar-lote",
    dependencies=[Depends(require_permission(_COMPRAS, "criar"))],
)
async def importar_lote_compras(arquivos: list[UploadFile] = File(...)):
    resultados = await _processar_lote_xml(arquivos, party_tag="emit")
    return {"data": resultados, "error": None}


@router.post(
    "/compras/importar",
    dependencies=[Depends(require_permission(_COMPRAS, "criar"))],
)
def criar_compra_importada(payload: CompraImportarXMLCreate, db: Session = Depends(get_db)):
    if not payload.parcelas:
        raise HTTPException(status_code=400, detail="Informe ao menos uma parcela.")

    compra = CompraFinanceira(
        fornecedor=payload.fornecedor,
        descricao=payload.descricao,
        valor_total=payload.valor_total,
        data_compra=payload.data_compra,
        numero_nf=payload.numero_nf,
    )
    db.add(compra)
    db.flush()

    total = len(payload.parcelas)
    descricao_base = payload.descricao or payload.fornecedor
    for i, parcela in enumerate(payload.parcelas, start=1):
        desc = descricao_base if total == 1 else f"{descricao_base} ({i}/{total})"
        db.add(
            Lancamento(
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
            )
        )

    db.commit()
    db.refresh(compra)
    return {"data": CompraFinanceiraOut.model_validate(compra), "error": None}


@router.get(
    "/compras/{compra_id}",
    dependencies=[Depends(require_permission(_COMPRAS, "ver"))],
)
def get_compra(compra_id: uuid.UUID, db: Session = Depends(get_db)):
    compra = (
        db.execute(
            select(CompraFinanceira)
            .where(CompraFinanceira.id == compra_id)
            .options(selectinload(CompraFinanceira.lancamentos).selectinload(Lancamento.anexos))
        )
        .scalars()
        .first()
    )
    if not compra:
        raise HTTPException(status_code=404, detail="Compra não encontrada")
    return {"data": CompraComLancamentosOut.model_validate(compra), "error": None}


@router.put(
    "/compras/{compra_id}",
    dependencies=[Depends(require_permission(_COMPRAS, "editar"))],
)
def atualizar_compra(compra_id: uuid.UUID, payload: CompraUpdate, db: Session = Depends(get_db)):
    compra = (
        db.execute(
            select(CompraFinanceira)
            .where(CompraFinanceira.id == compra_id)
            .options(selectinload(CompraFinanceira.lancamentos))
        )
        .scalars()
        .first()
    )
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


@router.delete(
    "/compras/{compra_id}",
    dependencies=[Depends(require_permission(_COMPRAS, "excluir"))],
)
def deletar_compra(compra_id: uuid.UUID, db: Session = Depends(get_db)):
    compra = (
        db.execute(
            select(CompraFinanceira)
            .where(CompraFinanceira.id == compra_id)
            .options(selectinload(CompraFinanceira.lancamentos).selectinload(Lancamento.anexos))
        )
        .scalars()
        .first()
    )
    if not compra:
        raise HTTPException(status_code=404, detail="Compra não encontrada")

    pagas = [lancamento for lancamento in compra.lancamentos if lancamento.status == "PAGO"]
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


@router.get("/vendas-financeiras", dependencies=[Depends(require_permission(_VENDAS, "ver"))])
def listar_vendas(db: Session = Depends(get_db)):
    rows = db.execute(select(VendaFinanceira).order_by(VendaFinanceira.data_venda.desc())).scalars().all()

    resultado = []
    for r in rows:
        total_parcelas = db.execute(select(func.count(Lancamento.id)).where(Lancamento.venda_id == r.id)).scalar() or 0
        parcelas_pagas = (
            db.execute(
                select(func.count(Lancamento.id)).where(
                    Lancamento.venda_id == r.id,
                    Lancamento.status == "PAGO",
                )
            ).scalar()
            or 0
        )
        resultado.append(
            VendaFinanceiraOut(
                id=r.id,
                cliente=r.cliente,
                descricao=r.descricao,
                valor_total=r.valor_total,
                data_venda=r.data_venda,
                nf_pdf_path=r.nf_pdf_path,
                created_at=r.created_at,
                total_parcelas=total_parcelas,
                parcelas_pagas=parcelas_pagas,
            )
        )

    return {"data": resultado, "error": None}


@router.post("/vendas-financeiras", dependencies=[Depends(require_permission(_VENDAS, "criar"))])
def criar_venda(payload: VendaCreate, db: Session = Depends(get_db)):
    venda = VendaFinanceira(
        cliente=payload.cliente,
        descricao=payload.descricao,
        valor_total=payload.valor_total,
        data_venda=payload.data_venda,
        numero_nf=payload.numero_nf,
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


@router.post(
    "/vendas-financeiras/importar-xml",
    dependencies=[Depends(require_permission(_VENDAS, "criar"))],
)
async def importar_xml_venda(arquivo: UploadFile = File(...)):
    conteudo = await arquivo.read()
    try:
        dados = _parse_nfe_xml(conteudo, party_tag="dest")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": NFeImportadaOut(**dados), "error": None}


@router.post(
    "/vendas-financeiras/importar-lote",
    dependencies=[Depends(require_permission(_VENDAS, "criar"))],
)
async def importar_lote_vendas(arquivos: list[UploadFile] = File(...)):
    resultados = await _processar_lote_xml(arquivos, party_tag="dest")
    return {"data": resultados, "error": None}


@router.post(
    "/vendas-financeiras/importar",
    dependencies=[Depends(require_permission(_VENDAS, "criar"))],
)
def criar_venda_importada(payload: VendaImportarXMLCreate, db: Session = Depends(get_db)):
    if not payload.parcelas:
        raise HTTPException(status_code=400, detail="Informe ao menos uma parcela.")

    venda = VendaFinanceira(
        cliente=payload.cliente,
        descricao=payload.descricao,
        valor_total=payload.valor_total,
        data_venda=payload.data_venda,
        numero_nf=payload.numero_nf,
    )
    db.add(venda)
    db.flush()

    total = len(payload.parcelas)
    descricao_base = payload.descricao or payload.cliente
    for i, parcela in enumerate(payload.parcelas, start=1):
        desc = descricao_base if total == 1 else f"{descricao_base} ({i}/{total})"
        db.add(
            Lancamento(
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
            )
        )

    db.commit()
    db.refresh(venda)
    return {"data": VendaFinanceiraOut.model_validate(venda), "error": None}


@router.get(
    "/vendas-financeiras/{venda_id}",
    dependencies=[Depends(require_permission(_VENDAS, "ver"))],
)
def get_venda(venda_id: uuid.UUID, db: Session = Depends(get_db)):
    venda = (
        db.execute(
            select(VendaFinanceira)
            .where(VendaFinanceira.id == venda_id)
            .options(selectinload(VendaFinanceira.lancamentos).selectinload(Lancamento.anexos))
        )
        .scalars()
        .first()
    )
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada")
    return {"data": VendaComLancamentosOut.model_validate(venda), "error": None}


@router.put(
    "/vendas-financeiras/{venda_id}",
    dependencies=[Depends(require_permission(_VENDAS, "editar"))],
)
def atualizar_venda(venda_id: uuid.UUID, payload: VendaUpdate, db: Session = Depends(get_db)):
    venda = (
        db.execute(
            select(VendaFinanceira)
            .where(VendaFinanceira.id == venda_id)
            .options(selectinload(VendaFinanceira.lancamentos))
        )
        .scalars()
        .first()
    )
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


@router.delete(
    "/vendas-financeiras/{venda_id}",
    dependencies=[Depends(require_permission(_VENDAS, "excluir"))],
)
def deletar_venda(venda_id: uuid.UUID, db: Session = Depends(get_db)):
    venda = (
        db.execute(
            select(VendaFinanceira)
            .where(VendaFinanceira.id == venda_id)
            .options(selectinload(VendaFinanceira.lancamentos).selectinload(Lancamento.anexos))
        )
        .scalars()
        .first()
    )
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada")

    pagas = [lancamento for lancamento in venda.lancamentos if lancamento.status == "PAGO"]
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


# ── DANFE Simplificada ────────────────────────────────────────────────────────


@router.post(
    "/danfe-simplificada",
    dependencies=[Depends(require_permission(_VENDAS, "gerar"))],
)
async def gerar_danfe_simplificada(arquivo: UploadFile = File(...), db: Session = Depends(get_db)):
    conteudo = await arquivo.read()
    try:
        dados = _parse_nfe_danfe(conteudo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    empresa = db.execute(select(Empresa)).scalars().first()
    pdf_bytes = gerar_danfe_simplificada_pdf(dados, empresa)

    numero_nf = dados["numero_nf"] or "SN"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="DANFE-{numero_nf}.pdf"'},
    )


# ── Upload de Anexos ──────────────────────────────────────────────────────────
# Anexos pertencem a lançamentos (financeiro_fluxo), mas na prática também
# são enviados a partir das telas de Compras e Vendas (ImportarXMLModal) —
# ver relatório final.


@router.post(
    "/lancamentos/{lancamento_id}/anexos",
    dependencies=[Depends(require_permission(_FLUXO, "criar"))],
)
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


@router.get(
    "/lancamentos/{lancamento_id}/anexos",
    dependencies=[Depends(require_permission(_FLUXO, "ver"))],
)
def listar_anexos(lancamento_id: uuid.UUID, db: Session = Depends(get_db)):
    lancamento = db.get(Lancamento, lancamento_id)
    if not lancamento:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    rows = (
        db.execute(
            select(AnexoLancamento)
            .where(AnexoLancamento.lancamento_id == lancamento_id)
            .order_by(AnexoLancamento.created_at)
        )
        .scalars()
        .all()
    )
    return {"data": [AnexoLancamentoOut.model_validate(r) for r in rows], "error": None}


@router.get(
    "/anexos/{anexo_id}/download",
    dependencies=[Depends(require_permission(_FLUXO, "ver"))],
)
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


@router.delete(
    "/anexos/{anexo_id}",
    dependencies=[Depends(require_permission(_FLUXO, "excluir"))],
)
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
# Não consumido por nenhuma página do frontend hoje (ver relatório final).


@router.get("/projecao", dependencies=[Depends(require_permission(_FLUXO, "ver"))])
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

        count = (
            db.execute(
                select(func.count(Lancamento.id)).where(
                    extract("month", Lancamento.data_vencimento) == mes,
                    extract("year", Lancamento.data_vencimento) == ano,
                )
            ).scalar()
            or 0
        )

        total_entrar = Decimal(str(entrar or 0))
        total_sair = Decimal(str(sair or 0))
        saldo_final = saldo_inicial + total_entrar - total_sair
        saldo_cascata = saldo_final

        resultado.append(
            ProjecaoMesOut(
                mes=mes,
                ano=ano,
                saldo_inicial=saldo_inicial,
                total_previsto_entrar=total_entrar,
                total_previsto_sair=total_sair,
                saldo_final_projetado=saldo_final,
                lancamentos_count=count,
            )
        )

    return {"data": resultado, "error": None}


# ── Métricas (dashboard) ────────────────────────────────────────────────────────

MESES_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _ultimos_meses(n: int) -> list[tuple[int, int]]:
    """Lista (ano, mes) dos últimos `n` meses, do mais antigo ao atual."""
    hoje = date.today()
    chaves = []
    m, a = hoje.month, hoje.year
    for _ in range(n):
        chaves.append((a, m))
        m -= 1
        if m == 0:
            m, a = 12, a - 1
    chaves.reverse()
    return chaves


def _serie_mensal_compras(db: Session, meses: int = 12) -> list[dict]:
    chaves = _ultimos_meses(meses)
    data_min = date(chaves[0][0], chaves[0][1], 1)

    rows = db.execute(
        select(
            func.strftime("%Y-%m", CompraFinanceira.data_compra).label("chave"),
            func.sum(CompraFinanceira.valor_total).label("total"),
        )
        .where(CompraFinanceira.data_compra >= data_min)
        .group_by("chave")
    ).all()
    mapa = {r.chave: float(r.total or 0) for r in rows}

    return [{"mes": m, "ano": a, "total": mapa.get(f"{a:04d}-{m:02d}", 0.0)} for a, m in chaves]


def _serie_mensal_por_fornecedor(db: Session, fornecedores: list[str], meses: int = 12) -> list[dict]:
    if not fornecedores:
        return []
    chaves = _ultimos_meses(meses)
    data_min = date(chaves[0][0], chaves[0][1], 1)

    rows = db.execute(
        select(
            func.strftime("%Y-%m", CompraFinanceira.data_compra).label("chave"),
            CompraFinanceira.fornecedor,
            func.sum(CompraFinanceira.valor_total).label("total"),
        )
        .where(
            CompraFinanceira.data_compra >= data_min,
            CompraFinanceira.fornecedor.in_(fornecedores),
        )
        .group_by("chave", CompraFinanceira.fornecedor)
    ).all()

    mapa: dict[str, dict[str, float]] = {}
    for r in rows:
        mapa.setdefault(r.chave, {})[r.fornecedor] = float(r.total or 0)

    resultado = []
    for a, m in chaves:
        chave = f"{a:04d}-{m:02d}"
        linha = {"mes": m, "ano": a, "label": f"{MESES_ABREV[m - 1]}/{str(a)[2:]}"}
        for f in fornecedores:
            linha[f] = mapa.get(chave, {}).get(f, 0.0)
        resultado.append(linha)
    return resultado


@router.get("/metricas-compras", dependencies=[Depends(require_permission(_PAINEL, "ver"))])
def metricas_compras(
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Métricas de compras para o dashboard executivo.

    total_compras/compras_por_fornecedor respeitam o período (padrão: mês
    atual). compras_por_mes e o volume por fornecedor são sempre a janela
    móvel dos últimos 12 meses — são gráficos de tendência, independentes
    do período selecionado.
    """
    if not data_inicio or not data_fim:
        hoje = date.today()
        data_inicio = hoje.replace(day=1)
        data_fim = date(hoje.year, hoje.month, monthrange(hoje.year, hoje.month)[1])

    compras_periodo = (
        db.execute(
            select(CompraFinanceira).where(
                CompraFinanceira.data_compra >= data_inicio,
                CompraFinanceira.data_compra <= data_fim,
            )
        )
        .scalars()
        .all()
    )

    total_compras = sum(float(c.valor_total or 0) for c in compras_periodo)

    fornecedor_map: dict[str, float] = {}
    for c in compras_periodo:
        fornecedor_map[c.fornecedor] = fornecedor_map.get(c.fornecedor, 0.0) + float(c.valor_total or 0)
    compras_por_fornecedor = [
        {
            "fornecedor": nome,
            "total": total,
            "percentual": (total / total_compras * 100) if total_compras else 0.0,
        }
        for nome, total in sorted(fornecedor_map.items(), key=lambda x: x[1], reverse=True)
    ]

    # Volume por fornecedor: não há rastreio de volume de tecido separado das
    # notas de compra — usa-se o total financeiro das compras como proxy,
    # sobre os últimos 12 meses (mesma janela do gráfico mensal).
    chaves_12m = _ultimos_meses(12)
    data_min_12m = date(chaves_12m[0][0], chaves_12m[0][1], 1)
    compras_12m = (
        db.execute(select(CompraFinanceira).where(CompraFinanceira.data_compra >= data_min_12m)).scalars().all()
    )

    fornecedor_vol: dict[str, dict] = {}
    for c in compras_12m:
        agg = fornecedor_vol.setdefault(c.fornecedor, {"fornecedor": c.fornecedor, "total_nfs": 0, "total_valor": 0.0})
        agg["total_nfs"] += 1
        agg["total_valor"] += float(c.valor_total or 0)
    volume_tecido_por_fornecedor = sorted(fornecedor_vol.values(), key=lambda x: x["total_valor"], reverse=True)[:5]
    top5_nomes = [f["fornecedor"] for f in volume_tecido_por_fornecedor]

    return {
        "data": {
            "total_compras": total_compras,
            "compras_por_fornecedor": compras_por_fornecedor,
            "compras_por_mes": _serie_mensal_compras(db, meses=12),
            "volume_tecido_por_fornecedor": volume_tecido_por_fornecedor,
            "volume_tecido_por_fornecedor_mes": _serie_mensal_por_fornecedor(db, top5_nomes, meses=12),
        },
        "error": None,
    }


@router.get("/metricas-resultado", dependencies=[Depends(require_permission(_PAINEL, "ver"))])
def metricas_resultado(db: Session = Depends(get_db)):
    """Receita × despesa × lucro (apenas lançamentos pagos) dos últimos 12 meses."""
    chaves = _ultimos_meses(12)
    data_min = date(chaves[0][0], chaves[0][1], 1)

    receita_rows = db.execute(
        select(
            func.strftime("%Y-%m", Lancamento.data_pagamento).label("chave"),
            func.sum(Lancamento.valor).label("total"),
        )
        .where(
            Lancamento.tipo == "RECEBER",
            Lancamento.status == "PAGO",
            Lancamento.data_pagamento >= data_min,
        )
        .group_by("chave")
    ).all()
    despesa_rows = db.execute(
        select(
            func.strftime("%Y-%m", Lancamento.data_pagamento).label("chave"),
            func.sum(Lancamento.valor).label("total"),
        )
        .where(
            Lancamento.tipo == "PAGAR",
            Lancamento.status == "PAGO",
            Lancamento.data_pagamento >= data_min,
        )
        .group_by("chave")
    ).all()

    receita_map = {r.chave: float(r.total or 0) for r in receita_rows}
    despesa_map = {r.chave: float(r.total or 0) for r in despesa_rows}

    resultado_por_mes = []
    for a, m in chaves:
        chave = f"{a:04d}-{m:02d}"
        receita = receita_map.get(chave, 0.0)
        despesa = despesa_map.get(chave, 0.0)
        resultado_por_mes.append(
            {
                "mes": m,
                "ano": a,
                "label": f"{MESES_ABREV[m - 1]}/{str(a)[2:]}",
                "receita": receita,
                "despesa": despesa,
                "lucro": receita - despesa,
            }
        )

    return {"data": {"resultado_por_mes": resultado_por_mes}, "error": None}


# ── Metas ─────────────────────────────────────────────────────────────────────
# Não consumido por nenhuma página do frontend hoje (ver relatório final).


@router.get("/metas", dependencies=[Depends(require_permission(_PAINEL, "ver"))])
def listar_metas(ano: Optional[int] = None, db: Session = Depends(get_db)):
    q = select(MetaMensal)
    if ano is not None:
        q = q.where(MetaMensal.ano == ano)
    q = q.order_by(MetaMensal.ano, MetaMensal.mes, MetaMensal.tipo)
    rows = db.execute(q).scalars().all()
    return {"data": [MetaMensalOut.model_validate(r) for r in rows], "error": None}


@router.post("/metas", dependencies=[Depends(require_permission(_PAINEL, "criar"))])
def criar_meta(payload: MetaMensalCreate, db: Session = Depends(get_db)):
    meta = MetaMensal(**payload.model_dump())
    db.add(meta)
    db.commit()
    db.refresh(meta)
    return {"data": MetaMensalOut.model_validate(meta), "error": None}


@router.put(
    "/metas/{meta_id}",
    dependencies=[Depends(require_permission(_PAINEL, "editar"))],
)
def atualizar_meta(meta_id: uuid.UUID, payload: MetaMensalUpdate, db: Session = Depends(get_db)):
    meta = db.get(MetaMensal, meta_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Meta não encontrada")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(meta, field, val)
    db.commit()
    db.refresh(meta)
    return {"data": MetaMensalOut.model_validate(meta), "error": None}


# ── Contabilidade ─────────────────────────────────────────────────────────────


def _anexo_nf_pdf(lancamentos: list[Lancamento]) -> Optional[AnexoLancamento]:
    """Primeiro anexo tipo='NF' que não seja, na prática, um XML (mesma regra
    usada no frontend para distinguir o PDF da NF do XML estruturado)."""
    for lanc in lancamentos:
        for anexo in lanc.anexos:
            if anexo.tipo == "NF" and not anexo.nome_original.lower().endswith(".xml"):
                return anexo
    return None


def _dados_contabilidade(db: Session, mes: int, ano: int) -> dict:
    vendas = (
        db.execute(
            select(VendaFinanceira)
            .where(
                extract("month", VendaFinanceira.data_venda) == mes,
                extract("year", VendaFinanceira.data_venda) == ano,
            )
            .options(selectinload(VendaFinanceira.lancamentos).selectinload(Lancamento.anexos))
            .order_by(VendaFinanceira.data_venda)
        )
        .scalars()
        .all()
    )

    notas_venda = []
    for v in vendas:
        anexo = _anexo_nf_pdf(v.lancamentos)
        if not anexo:
            continue
        notas_venda.append(
            {
                "id": v.id,
                "cliente": v.cliente,
                "numero_nf": v.numero_nf,
                "data_venda": v.data_venda,
                "valor_total": v.valor_total,
                "nf_pdf_path": anexo.arquivo_path,
                "nf_nome": anexo.nome_original,
            }
        )

    compras = (
        db.execute(
            select(CompraFinanceira)
            .where(
                extract("month", CompraFinanceira.data_compra) == mes,
                extract("year", CompraFinanceira.data_compra) == ano,
            )
            .options(selectinload(CompraFinanceira.lancamentos).selectinload(Lancamento.anexos))
            .order_by(CompraFinanceira.data_compra)
        )
        .scalars()
        .all()
    )

    notas_compra = []
    for c in compras:
        anexo = _anexo_nf_pdf(c.lancamentos)
        if not anexo:
            continue
        notas_compra.append(
            {
                "id": c.id,
                "fornecedor": c.fornecedor,
                "numero_nf": c.numero_nf,
                "data_compra": c.data_compra,
                "valor_total": c.valor_total,
                "nf_pdf_path": anexo.arquivo_path,
                "nf_nome": anexo.nome_original,
            }
        )

    lancs_pagos = (
        db.execute(
            select(Lancamento)
            .where(
                Lancamento.status == "PAGO",
                extract("month", Lancamento.data_pagamento) == mes,
                extract("year", Lancamento.data_pagamento) == ano,
            )
            .options(
                selectinload(Lancamento.anexos),
                selectinload(Lancamento.compra)
                .selectinload(CompraFinanceira.lancamentos)
                .selectinload(Lancamento.anexos),
                selectinload(Lancamento.venda)
                .selectinload(VendaFinanceira.lancamentos)
                .selectinload(Lancamento.anexos),
            )
            .order_by(Lancamento.data_pagamento)
        )
        .scalars()
        .all()
    )

    boletos_pagos = []
    for lancamento in lancs_pagos:
        boleto = next((a for a in lancamento.anexos if a.tipo == "BOLETO"), None)
        if not boleto:
            continue

        if lancamento.compra:
            fornecedor_cliente = lancamento.compra.fornecedor
            numero_nf = lancamento.compra.numero_nf
            nf_anexo = _anexo_nf_pdf(lancamento.compra.lancamentos)
        elif lancamento.venda:
            fornecedor_cliente = lancamento.venda.cliente
            numero_nf = lancamento.venda.numero_nf
            nf_anexo = _anexo_nf_pdf(lancamento.venda.lancamentos)
        else:
            fornecedor_cliente = lancamento.descricao
            numero_nf = None
            nf_anexo = None

        boletos_pagos.append(
            {
                "lancamento_id": lancamento.id,
                "descricao": lancamento.descricao,
                "fornecedor_cliente": fornecedor_cliente,
                "numero_nf": numero_nf,
                "data_pagamento": lancamento.data_pagamento,
                "valor": lancamento.valor,
                "parcela_numero": lancamento.parcela_numero,
                "parcela_total": lancamento.parcela_total,
                "boleto_pdf_path": boleto.arquivo_path,
                "boleto_nome": boleto.nome_original,
                "nf_pdf_path": nf_anexo.arquivo_path if nf_anexo else None,
                "nf_nome": nf_anexo.nome_original if nf_anexo else None,
            }
        )

    return {
        "mes": mes,
        "ano": ano,
        "notas_venda": notas_venda,
        "notas_compra": notas_compra,
        "boletos_pagos": boletos_pagos,
    }


@router.get("/contabilidade", dependencies=[Depends(require_permission(_CONTABIL, "ver"))])
def contabilidade(mes: int, ano: int, db: Session = Depends(get_db)):
    dados = _dados_contabilidade(db, mes, ano)
    return {"data": ContabilidadeMesOut(**dados), "error": None}


@router.post(
    "/contabilidade/gerar-pacote",
    dependencies=[Depends(require_permission(_CONTABIL, "gerar"))],
)
def gerar_pacote_contabil(payload: ContabilidadeGerarPacoteIn, db: Session = Depends(get_db)):
    dados = _dados_contabilidade(db, payload.mes, payload.ano)
    empresa = db.execute(select(Empresa)).scalars().first()
    zip_bytes = montar_pacote_zip(dados, empresa)
    nome = f"Contabilidade-{payload.mes:02d}-{payload.ano}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.post(
    "/contabilidade/resumo-interno",
    dependencies=[Depends(require_permission(_CONTABIL, "gerar"))],
)
def resumo_interno_contabil(payload: ContabilidadeGerarPacoteIn, db: Session = Depends(get_db)):
    dados = _dados_contabilidade(db, payload.mes, payload.ano)
    empresa = db.execute(select(Empresa)).scalars().first()
    pdf_bytes = gerar_resumo_interno_pdf(dados, empresa)
    nome = f"Resumo-Interno-{payload.mes:02d}-{payload.ano}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
