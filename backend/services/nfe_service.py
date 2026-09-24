import os
import random
import tempfile
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from lxml import etree
from reportlab.graphics.barcode.code128 import Code128
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from config import settings
from models.cliente import Cliente  # noqa: F401 — referência futura (ver limitações no fim do arquivo)
from models.nfe import NotaFiscal
from models.pedido import ItemPedido, PedidoVenda
from models.produto import Produto
from models.tes import TES
from models.venda import Empresa
from services.segredo_service import decifrar_segredo

NFE_NS = "http://www.portalfiscal.inf.br/nfe"
NSMAP = {None: NFE_NS}

# Estrutura de pastas — caminhos relativos ao cwd do processo (mesma
# convenção de uploads/logos em routers/configuracao_empresa.py). O processo
# roda com cwd = backend/, então "../Certificados" fica na raiz do projeto.
# Item 4.1: o .pfx NÃO vive mais ao lado do código — o caminho vem da
# configuração da empresa (escolhido pelo usuário; no desktop via diálogo
# nativo). A pasta padrão (quando definida por CERTIFICADO_DIR) é criada
# abaixo sem depender de caminho relativo à raiz do projeto.
_NFE_BASE = "uploads/nfe"
_PASTAS_NFE = [
    "Enviadas",
    "Geradas",
    "Retorno",
    "Recibos",
    "RetCanceladas",
    "SolicCancelamento",
    "CartasDeCorrecaoEnviadas",
    "LotesGerados",
    "Schemas",
]

_URLS_SEFAZ_RS = {
    "Homologacao": "https://nfe-homologacao.sefazrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx",
    "Producao": "https://nfe.sefazrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx",
}

# CSOSN cobertos na montagem do grupo ICMSSN — os demais valores válidos de
# CSOSN (101, 103, 201, 202, 203, 300, 900) ainda não têm builder e caem no
# ValueError abaixo, conforme pedido ("cobrir os principais").
_CSOSN_SUPORTADOS = ("102", "400", "500")

_MODFRETE_POR_TIPO = {
    "CIF": "0",
    "FOB": "1",
    "Por conta de terceiros": "2",
    "Próprio": "3",
    "Sem Frete": "9",
    "Sem Ocorrência": "9",
}


# ─────────────────────────────────────────────────────────────────────────
# FUNÇÃO 1 — estrutura de pastas
# ─────────────────────────────────────────────────────────────────────────


def criar_pastas_nfe() -> None:
    for nome in _PASTAS_NFE:
        os.makedirs(os.path.join(_NFE_BASE, nome), exist_ok=True)
    os.makedirs(pasta_certificados_padrao(), exist_ok=True)


def pasta_certificados_padrao() -> str:
    """Pasta convencional dos certificados digitais (item 4.1).

    Prioridade:
      1. ``CERTIFICADO_DIR`` (settings/ambiente) — no desktop o Electron
         injeta ``<userData>/Certificados`` (fora da árvore de código).
      2. Sem override: a pasta ``Certificados/`` na raiz do repositório
         (convenção do projeto, decidida com o usuário). Resolvida via
         ``__file__`` — NUNCA via ``cwd``, que era o "bug" que quebrava a
         localização no app empacotado (cwd = userData).
    """
    if settings.certificado_dir:
        return settings.certificado_dir
    # backend/services/nfe_service.py -> backend/ -> raiz do projeto
    raiz_repo = Path(__file__).resolve().parents[2]
    return str(raiz_repo / "Certificados")


# ─────────────────────────────────────────────────────────────────────────
# FUNÇÃO 2 — numeração sequencial por série
# ─────────────────────────────────────────────────────────────────────────


def proximo_numero(db: Session, empresa: Empresa, serie: str) -> int:
    """Incrementa e persiste o contador certo (NF-e ou NFC-e) conforme a
    série informada bater com nfe_serie_padrao/nfce_serie_padrao da Empresa.
    Séries que não batem com nenhuma (ex.: "ORC") usam o contador de NF-e."""
    if serie == empresa.nfce_serie_padrao:
        empresa.nfce_numero_atual += 1
        numero = empresa.nfce_numero_atual
    else:
        empresa.nfe_numero_atual += 1
        numero = empresa.nfe_numero_atual
    db.commit()
    db.refresh(empresa)
    return numero


# ─────────────────────────────────────────────────────────────────────────
# Chave de acesso
# ─────────────────────────────────────────────────────────────────────────


def _somente_digitos(v) -> str:
    return "".join(c for c in str(v or "") if c.isdigit())


def _mod11_dv(chave43: str) -> int:
    """Dígito verificador módulo 11 da chave de acesso (pesos 2..9 cíclicos,
    da direita para a esquerda). Algoritmo padrão do manual da NF-e — não foi
    possível validar contra uma chave real de referência neste ambiente
    (ver limitações no fim do arquivo); revisar contra um caso de
    homologação real antes de transmitir de verdade."""
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = 0
    for i, c in enumerate(reversed(chave43)):
        soma += int(c) * pesos[i % 8]
    resto = soma % 11
    return 0 if resto in (0, 1) else 11 - resto


def _gerar_cnf() -> str:
    return f"{random.randint(0, 99999999):08d}"


def montar_chave_acesso(empresa: Empresa, nfe: NotaFiscal, cnf: str) -> str:
    cuf = "43"  # RS
    aamm = nfe.data_emissao.strftime("%y%m")
    cnpj = _somente_digitos(empresa.cnpj).zfill(14)
    mod = nfe.modelo
    serie = str(nfe.serie).zfill(3)
    nnf = str(nfe.numero).zfill(9)
    tpemis = "1"
    chave43 = f"{cuf}{aamm}{cnpj}{mod}{serie}{nnf}{tpemis}{cnf}"
    dv = _mod11_dv(chave43)
    return f"{chave43}{dv}"


# ─────────────────────────────────────────────────────────────────────────
# FUNÇÃO 3 — montagem do XML
# ─────────────────────────────────────────────────────────────────────────


def _sub(parent, tag, text=None):
    el = etree.SubElement(parent, tag)
    if text is not None:
        el.text = str(text)
    return el


def _valor(v) -> str:
    return f"{Decimal(str(v or 0)):.2f}"


def _quantidade_item(item: ItemPedido) -> int:
    return (
        (item.qtd_p or 0)
        + (item.qtd_m or 0)
        + (item.qtd_g or 0)
        + (item.qtd_gg or 0)
        + (item.qtd_g1 or 0)
        + (item.qtd_g2 or 0)
        + (item.qtd_g3 or 0)
    )


def _tes_do_item(db: Session, item: ItemPedido, pedido: PedidoVenda) -> TES | None:
    tes_id = item.tes_id or pedido.tes_id
    if tes_id is None:
        return None
    return db.get(TES, tes_id)


def _montar_icms_sn(parent, item: ItemPedido, produto: Produto | None, tes: TES) -> None:
    """ICMSSN — cobre CSOSN 102, 400 e 500 (ver _CSOSN_SUPORTADOS). Outros
    valores válidos de CSOSN existem no cadastro de TES mas não têm builder
    aqui ainda; melhor recusar com erro claro do que emitir um XML errado."""
    if tes.csosn not in _CSOSN_SUPORTADOS:
        raise ValueError(
            f"CSOSN '{tes.csosn}' do TES '{tes.codigo}' ainda não é suportado na "
            f"montagem do XML da NF-e. Suportados nesta versão: {', '.join(_CSOSN_SUPORTADOS)}."
        )

    icms = _sub(parent, "ICMS")
    grupo = _sub(icms, f"ICMSSN{tes.csosn}")
    orig = str(produto.origem) if produto and produto.origem is not None else (tes.origem or "0")
    _sub(grupo, "orig", orig)
    _sub(grupo, "CSOSN", tes.csosn)

    if tes.csosn == "400":
        return  # ICMSSN400 só tem orig + CSOSN

    if tes.csosn == "500":
        _sub(grupo, "vBCSTRet", "0.00")
        _sub(grupo, "vICMSSTRet", "0.00")
        return

    if tes.csosn == "102":
        return  # ICMSSN102 também só tem orig + CSOSN


def montar_xml_nfe(pedido: PedidoVenda | None, nfe: NotaFiscal, empresa: Empresa, db: Session) -> str:
    """Monta o XML da NF-e (modelo 55, Simples Nacional) a partir do pedido
    e da configuração fiscal da empresa. Constrói a árvore diretamente com
    lxml (em vez das dataclasses do nfelib) — ver nota de limitações no fim
    do arquivo sobre essa escolha."""
    itens = [i for i in (pedido.itens if pedido else []) if i.produto_id is not None]
    if pedido and not itens:
        raise ValueError(
            "O pedido não tem nenhum item com produto_id preenchido — "
            "a NF-e exige produto cadastrado (NCM/CEST/unidade) por item."
        )

    cnf = _gerar_cnf()
    chave = montar_chave_acesso(empresa, nfe, cnf)
    nfe.chave_acesso = chave

    root = etree.Element("NFe", nsmap=NSMAP)
    infNFe = _sub(root, "infNFe")
    infNFe.set("Id", f"NFe{chave}")
    infNFe.set("versao", "4.00")

    # ── ide ──────────────────────────────────────────────────────────────
    ide = _sub(infNFe, "ide")
    _sub(ide, "cUF", "43")
    _sub(ide, "cNF", cnf)
    primeiro_tes = _tes_do_item(db, itens[0], pedido) if itens else None
    _sub(ide, "natOp", primeiro_tes.natureza_operacao if primeiro_tes else "Venda de mercadoria")
    _sub(ide, "mod", nfe.modelo)
    _sub(ide, "serie", nfe.serie)
    _sub(ide, "nNF", str(nfe.numero))
    _sub(ide, "dhEmi", nfe.data_emissao.strftime("%Y-%m-%dT%H:%M:%S-03:00"))
    if nfe.data_saida:
        hora = nfe.hora_saida or "00:00:00"
        _sub(ide, "dhSaiEnt", f"{nfe.data_saida.strftime('%Y-%m-%d')}T{hora}-03:00")
    _sub(ide, "tpNF", "1")
    uf_cliente = pedido.cliente_uf if pedido else None
    id_dest = "1" if (not uf_cliente or uf_cliente == empresa.uf_emitente) else "2"
    _sub(ide, "idDest", id_dest)
    _sub(ide, "cMunFG", empresa.codigo_ibge_municipio or "")
    _sub(ide, "tpImp", "1")
    _sub(ide, "tpEmis", "1")
    tp_amb = "2" if empresa.ambiente_sefaz == "Homologacao" else "1"
    _sub(ide, "tpAmb", tp_amb)
    _sub(ide, "finNFe", "1")
    _sub(ide, "indFinal", "1")
    indpres_map = {"Presencial": "1", "Internet": "2", "Teleatendimento": "3", "Outros": "9"}
    _sub(ide, "indPres", indpres_map.get(pedido.indicador_presenca if pedido else "Presencial", "9"))
    _sub(ide, "procEmi", "0")
    _sub(ide, "verProc", "SmartCut 1.0")

    # ── emit ─────────────────────────────────────────────────────────────
    emit = _sub(infNFe, "emit")
    _sub(emit, "CNPJ", _somente_digitos(empresa.cnpj))
    _sub(emit, "xNome", empresa.razao_social or "")
    _sub(emit, "xFant", empresa.razao_social or "")
    end_emit = _sub(emit, "enderEmit")
    _sub(end_emit, "xLgr", empresa.endereco or "")
    _sub(end_emit, "nro", empresa.endereco_numero or "S/N")
    _sub(end_emit, "xBairro", empresa.endereco_bairro or "")
    _sub(end_emit, "cMun", empresa.codigo_ibge_municipio or "")
    _sub(end_emit, "xMun", empresa.cidade or "")
    _sub(end_emit, "UF", empresa.uf_emitente)
    _sub(end_emit, "CEP", _somente_digitos(empresa.cep))
    _sub(end_emit, "cPais", empresa.codigo_pais or "1058")
    _sub(end_emit, "xPais", "Brasil")
    if empresa.ie:
        _sub(emit, "IE", _somente_digitos(empresa.ie))
    _sub(emit, "CRT", "1")

    # ── dest ─────────────────────────────────────────────────────────────
    dest = _sub(infNFe, "dest")
    doc_cliente = _somente_digitos(pedido.cliente_cnpj) if pedido else ""
    if len(doc_cliente) == 14:
        _sub(dest, "CNPJ", doc_cliente)
    elif len(doc_cliente) == 11:
        _sub(dest, "CPF", doc_cliente)
    _sub(dest, "xNome", (pedido.cliente_razao_social if pedido else None) or "Consumidor")
    end_dest = _sub(dest, "enderDest")
    _sub(end_dest, "xLgr", (pedido.cliente_endereco if pedido else None) or "")
    _sub(end_dest, "nro", (pedido.cliente_numero if pedido else None) or "S/N")
    _sub(end_dest, "xBairro", (pedido.cliente_bairro if pedido else None) or "")
    _sub(end_dest, "cMun", (pedido.cliente_codigo_ibge_municipio if pedido else None) or "")
    _sub(end_dest, "xMun", (pedido.cliente_cidade if pedido else None) or "")
    _sub(end_dest, "UF", uf_cliente or empresa.uf_emitente)
    _sub(end_dest, "CEP", _somente_digitos(pedido.cliente_cep if pedido else None))
    _sub(end_dest, "cPais", (pedido.cliente_codigo_pais if pedido else None) or "1058")
    _sub(end_dest, "xPais", "Brasil")
    cliente_ie = _somente_digitos(pedido.cliente_ie) if pedido else ""
    if cliente_ie:
        _sub(dest, "IE", cliente_ie)
        _sub(dest, "indIEDest", "1")
    else:
        _sub(dest, "indIEDest", "9")
    if pedido and pedido.cliente_email:
        _sub(dest, "email", pedido.cliente_email)

    # ── det (itens) ──────────────────────────────────────────────────────
    v_prod_total = Decimal("0")
    for n_item, item in enumerate(itens, start=1):
        produto = db.get(Produto, item.produto_id)
        tes = _tes_do_item(db, item, pedido)
        if tes is None:
            raise ValueError(f"Item {n_item} não tem TES definido (nem no item, nem no cabeçalho do pedido).")

        det = _sub(infNFe, "det")
        det.set("nItem", str(n_item))
        prod = _sub(det, "prod")
        _sub(prod, "cProd", produto.codigo)
        _sub(prod, "cEAN", produto.cod_barras or "SEM GTIN")
        _sub(prod, "xProd", produto.descricao)
        _sub(prod, "NCM", _somente_digitos(produto.ncm).zfill(8) if produto.ncm else "")
        _sub(prod, "CFOP", tes.cfop)
        _sub(prod, "uCom", produto.unidade)
        qtd = _quantidade_item(item)
        _sub(prod, "qCom", f"{qtd:.4f}")
        _sub(prod, "vUnCom", _valor(item.preco_unitario))
        v_prod = Decimal(str(item.preco_total or 0))
        v_prod_total += v_prod
        _sub(prod, "vProd", _valor(v_prod))
        _sub(prod, "cEANTrib", produto.cod_barras or "SEM GTIN")
        _sub(prod, "uTrib", produto.unidade)
        _sub(prod, "qTrib", f"{qtd:.4f}")
        _sub(prod, "vUnTrib", _valor(item.preco_unitario))
        _sub(prod, "indTot", "1")

        imposto = _sub(det, "imposto")
        _montar_icms_sn(imposto, item, produto, tes)
        pis = _sub(imposto, "PIS")
        pisnt = _sub(pis, "PISNT")
        _sub(pisnt, "CST", "07")
        cofins = _sub(imposto, "COFINS")
        cofinsnt = _sub(cofins, "COFINSNT")
        _sub(cofinsnt, "CST", "07")

    # ── total ────────────────────────────────────────────────────────────
    total = _sub(infNFe, "total")
    icms_tot = _sub(total, "ICMSTot")
    for tag in ("vBC", "vICMS", "vICMSDeson", "vFCP", "vBCST", "vST", "vFCPST", "vFCPSTRet"):
        _sub(icms_tot, tag, "0.00")
    _sub(icms_tot, "vProd", _valor(v_prod_total))
    v_frete = pedido.valor_frete if pedido else 0
    v_seguro = pedido.valor_seguro if pedido else 0
    v_desc = pedido.desconto_geral_valor if pedido else 0
    v_outro = pedido.valor_despesas if pedido else 0
    _sub(icms_tot, "vFrete", _valor(v_frete))
    _sub(icms_tot, "vSeg", _valor(v_seguro))
    _sub(icms_tot, "vDesc", _valor(v_desc))
    for tag in ("vII", "vIPI", "vIPIDevol", "vPIS", "vCOFINS"):
        _sub(icms_tot, tag, "0.00")
    _sub(icms_tot, "vOutro", _valor(v_outro))
    v_nf = v_prod_total + Decimal(str(v_frete)) + Decimal(str(v_seguro)) + Decimal(str(v_outro)) - Decimal(str(v_desc))
    _sub(icms_tot, "vNF", _valor(v_nf))
    nfe.valor_nf = float(v_nf)

    # ── transp ───────────────────────────────────────────────────────────
    transp = _sub(infNFe, "transp")
    mod_frete = _MODFRETE_POR_TIPO.get(pedido.tipo_frete if pedido else None, "9")
    _sub(transp, "modFrete", mod_frete)
    if pedido and pedido.transportadora_id:
        transportadora = pedido.transportadora
        if transportadora:
            transporta = _sub(transp, "transporta")
            doc_transp = _somente_digitos(getattr(transportadora, "cpf_cnpj", None))
            if len(doc_transp) == 14:
                _sub(transporta, "CNPJ", doc_transp)
            elif len(doc_transp) == 11:
                _sub(transporta, "CPF", doc_transp)
            _sub(transporta, "xNome", getattr(transportadora, "nome", None) or "")
            if getattr(transportadora, "rg_ie", None):
                _sub(transporta, "IE", transportadora.rg_ie)
            _sub(transporta, "xEnder", getattr(transportadora, "endereco", None) or "")
            _sub(transporta, "xMun", getattr(transportadora, "municipio", None) or "")
            _sub(transporta, "UF", getattr(transportadora, "estado", None) or "")
    if pedido and pedido.qtd_volumes > 0:
        vol = _sub(transp, "vol")
        _sub(vol, "qVol", str(pedido.qtd_volumes))
        if pedido.especie_volumes:
            _sub(vol, "esp", pedido.especie_volumes)
        if pedido.peso_liquido:
            _sub(vol, "pesoL", f"{pedido.peso_liquido:.3f}")
        if pedido.peso_bruto:
            _sub(vol, "pesoB", f"{pedido.peso_bruto:.3f}")

    # ── infAdic ──────────────────────────────────────────────────────────
    partes_info = []
    if pedido and pedido.informacoes_adicionais:
        partes_info.append(pedido.informacoes_adicionais)
    if tp_amb == "2":
        partes_info.append("NOTA FISCAL EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL")
    if partes_info:
        inf_adic = _sub(infNFe, "infAdic")
        _sub(inf_adic, "infCpl", " | ".join(partes_info))

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8").decode("utf-8")


# ─────────────────────────────────────────────────────────────────────────
# FUNÇÃO 4 — assinatura digital
# ─────────────────────────────────────────────────────────────────────────


class _NFeXMLSigner:
    """signxml bloqueia SHA1 por padrão (considerado inseguro), mas o
    perfil de assinatura da NF-e exige RSA-SHA1/SHA1/C14N-1.0 — não há
    alternativa aceita pela SEFAZ. Este wrapper reativa SHA1 apenas para
    este uso específico."""

    def __new__(cls):
        from signxml import XMLSigner

        class _Signer(XMLSigner):
            def check_deprecated_methods(self):
                pass

        return _Signer


def _carregar_certificado(empresa: Empresa):
    from cryptography.hazmat.primitives.serialization import pkcs12

    if not empresa.certificado_path or not os.path.exists(empresa.certificado_path):
        raise ValueError("Certificado digital não configurado ou arquivo .pfx não encontrado.")
    if not empresa.certificado_senha:
        raise ValueError("Senha do certificado não configurada.")

    senha = decifrar_segredo(empresa.certificado_senha)
    with open(empresa.certificado_path, "rb") as f:
        dados_pfx = f.read()
    try:
        private_key, certificate, _ = pkcs12.load_key_and_certificates(dados_pfx, senha.encode("utf-8"))
    except Exception as e:
        raise ValueError(f"Não foi possível abrir o certificado: {e}") from e
    if private_key is None or certificate is None:
        raise ValueError("Certificado .pfx não contém chave privada e certificado válidos.")
    return private_key, certificate


def _assinar_elemento(root, elemento_com_id, empresa: Empresa):
    """Assina `elemento_com_id` (deve ter atributo Id) dentro de `root`,
    usando o perfil RSA-SHA1/SHA1/C14N-1.0 exigido pela SEFAZ."""
    from signxml import CanonicalizationMethod, DigestAlgorithm, SignatureMethod, methods

    private_key, certificate = _carregar_certificado(empresa)
    elemento_id = elemento_com_id.get("Id")

    signer_cls = _NFeXMLSigner()
    signer = signer_cls(
        method=methods.enveloped,
        signature_algorithm=SignatureMethod.RSA_SHA1,
        digest_algorithm=DigestAlgorithm.SHA1,
        c14n_algorithm=CanonicalizationMethod.CANONICAL_XML_1_0,
    )
    return signer.sign(
        root,
        key=private_key,
        cert=[certificate],
        reference_uri=f"#{elemento_id}",
        id_attribute="Id",
    )


def assinar_xml(xml_str: str, empresa: Empresa) -> str:
    root = etree.fromstring(xml_str.encode("utf-8"))
    ns = {"n": NFE_NS}
    infNFe = root.find("n:infNFe", ns)
    signed_root = _assinar_elemento(root, infNFe, empresa)
    return etree.tostring(signed_root, xml_declaration=True, encoding="UTF-8").decode("utf-8")


# ─────────────────────────────────────────────────────────────────────────
# Eventos (cancelamento / carta de correção) — estrutura simplificada.
# Não seguem o XSD de eventos da NF-e com precisão total (ver limitações
# no fim do arquivo); cobrem o suficiente para persistir e assinar
# localmente, mas o envio real do evento à SEFAZ (webservice
# RecepcaoEvento, distinto do NFeAutorizacao4 usado em transmitir_nfe)
# não foi implementado nesta versão.
# ─────────────────────────────────────────────────────────────────────────


def _montar_evento(
    empresa: Empresa, nfe: NotaFiscal, tp_evento: str, n_seq_evento: str, detalhe_tag: str, detalhe_conteudo: dict
) -> str:
    cnpj = _somente_digitos(empresa.cnpj).zfill(14)
    dh_evento = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")
    id_evento = f"ID{tp_evento}{nfe.chave_acesso}{n_seq_evento.zfill(2)}"

    root = etree.Element("evento", nsmap=NSMAP)
    root.set("versao", "1.00")
    inf_evento = _sub(root, "infEvento")
    inf_evento.set("Id", id_evento)
    _sub(inf_evento, "cOrgao", "43")
    tp_amb = "2" if empresa.ambiente_sefaz == "Homologacao" else "1"
    _sub(inf_evento, "tpAmb", tp_amb)
    _sub(inf_evento, "CNPJ", cnpj)
    _sub(inf_evento, "chNFe", nfe.chave_acesso)
    _sub(inf_evento, "dhEvento", dh_evento)
    _sub(inf_evento, "tpEvento", tp_evento)
    _sub(inf_evento, "nSeqEvento", n_seq_evento)
    _sub(inf_evento, "verEvento", "1.00")
    det_evento = _sub(inf_evento, "detEvento")
    det_evento.set("versao", "1.00")
    _sub(det_evento, "descEvento", detalhe_conteudo.pop("descEvento"))
    for tag, valor in detalhe_conteudo.items():
        _sub(det_evento, tag, valor)

    xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8").decode("utf-8")
    root_parsed = etree.fromstring(xml.encode("utf-8"))
    signed = _assinar_elemento(root_parsed, root_parsed.find(f"{{{NFE_NS}}}infEvento"), empresa)
    return etree.tostring(signed, xml_declaration=True, encoding="UTF-8").decode("utf-8")


def montar_evento_cancelamento(empresa: Empresa, nfe: NotaFiscal, justificativa: str) -> str:
    if len(justificativa) < 15:
        raise ValueError("Justificativa de cancelamento deve ter no mínimo 15 caracteres.")
    return _montar_evento(
        empresa,
        nfe,
        tp_evento="110111",
        n_seq_evento="1",
        detalhe_tag="evCancNFe",
        detalhe_conteudo={
            "descEvento": "Cancelamento",
            "nProt": nfe.protocolo or "",
            "xJust": justificativa,
        },
    )


def montar_evento_cce(empresa: Empresa, nfe: NotaFiscal, correcao: str) -> str:
    if len(correcao) < 15:
        raise ValueError("Texto da carta de correção deve ter no mínimo 15 caracteres.")
    return _montar_evento(
        empresa,
        nfe,
        tp_evento="110110",
        n_seq_evento="1",
        detalhe_tag="evCCe",
        detalhe_conteudo={
            "descEvento": "Carta de Correção",
            "xCorrecao": correcao,
            "xCondUso": (
                "A Carta de Correcao e disciplinada pelo paragrafo 1o-A do art. 7 "
                "do Convenio S/N, de 15 de dezembro de 1970 e pode ser utilizada para "
                "regularizacao de erro ocorrido na emissao de documento fiscal, desde "
                "que o erro nao esteja relacionado com: I - as variaveis que determinam "
                "o valor do imposto tais como: base de calculo, aliquota, diferenca de "
                "preco, quantidade, valor da operacao ou da prestacao; II - a correcao "
                "de dados cadastrais que implique mudanca do remetente ou do "
                "destinatario; III - a data de emissao ou de saida."
            ),
        },
    )


# ─────────────────────────────────────────────────────────────────────────
# FUNÇÃO 5 — transmissão SEFAZ-RS
# ─────────────────────────────────────────────────────────────────────────


def transmitir_nfe(xml_assinado: str, empresa: Empresa) -> dict:
    """Envia o lote (de 1 NF-e) para o webservice de autorização da
    SEFAZ-RS. Constrói o client zeep com o certificado do cliente (mTLS),
    extraído do .pfx para arquivos PEM temporários (requests não aceita
    bytes em memória para client cert). Ver limitações no fim do arquivo —
    esta função não pôde ser testada contra a SEFAZ real."""
    import requests
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    from zeep import Client
    from zeep.transports import Transport

    if not empresa.certificado_path or not os.path.exists(empresa.certificado_path):
        raise ValueError("Certificado digital não configurado ou arquivo .pfx não encontrado.")

    senha = decifrar_segredo(empresa.certificado_senha)
    with open(empresa.certificado_path, "rb") as f:
        dados_pfx = f.read()
    private_key, certificate, _ = pkcs12.load_key_and_certificates(dados_pfx, senha.encode("utf-8"))

    url = _URLS_SEFAZ_RS.get(empresa.ambiente_sefaz)
    if not url:
        raise ValueError(f"Ambiente SEFAZ inválido: {empresa.ambiente_sefaz}")

    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    with (
        tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as cert_f,
        tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as key_f,
    ):
        cert_f.write(cert_pem)
        key_f.write(key_pem)
        cert_path, key_path = cert_f.name, key_f.name

    try:
        session = requests.Session()
        session.cert = (cert_path, key_path)
        transport = Transport(session=session)
        client = Client(f"{url}?WSDL", transport=transport)

        lote_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
            f"<idLote>1</idLote><indSinc>1</indSinc>{xml_assinado}</enviNFe>"
        )
        resposta = client.service.nfeAutorizacaoLote(nfeDadosMsg=lote_xml)
        resposta_str = str(resposta)

        resp_root = etree.fromstring(resposta_str.encode("utf-8")) if resposta_str.strip().startswith("<") else None
        cstat = xmotivo = protocolo = dh_recbto = None
        if resp_root is not None:
            ns = {"n": NFE_NS}
            cstat_el = resp_root.find(".//n:cStat", ns)
            xmotivo_el = resp_root.find(".//n:xMotivo", ns)
            protocolo_el = resp_root.find(".//n:nProt", ns)
            dh_el = resp_root.find(".//n:dhRecbto", ns)
            cstat = cstat_el.text if cstat_el is not None else None
            xmotivo = xmotivo_el.text if xmotivo_el is not None else None
            protocolo = protocolo_el.text if protocolo_el is not None else None
            dh_recbto = dh_el.text if dh_el is not None else None

        return {
            "cStat": cstat,
            "xMotivo": xmotivo,
            "protocolo": protocolo,
            "dhRecbto": dh_recbto,
            "raw": resposta_str,
        }
    finally:
        os.unlink(cert_path)
        os.unlink(key_path)


# ─────────────────────────────────────────────────────────────────────────
# FUNÇÃO 6 — DANFE em PDF
# ─────────────────────────────────────────────────────────────────────────

_D_TITULO = ParagraphStyle("d_titulo", fontName="Helvetica-Bold", fontSize=11, leading=14)
_D_N = ParagraphStyle("d_n", fontName="Helvetica", fontSize=8, leading=10)
_D_B = ParagraphStyle("d_b", fontName="Helvetica-Bold", fontSize=8, leading=10)
_D_LBL = ParagraphStyle(
    "d_lbl", fontName="Helvetica-Bold", fontSize=6, leading=7.5, textColor=colors.Color(0.4, 0.4, 0.4)
)
_D_HDR = ParagraphStyle(
    "d_hdr", fontName="Helvetica-Bold", fontSize=7.5, leading=9, alignment=1, textColor=colors.white
)
_D_CAP = ParagraphStyle("d_cap", fontName="Helvetica", fontSize=7, leading=9, alignment=1)


def _brl(v) -> str:
    s = f"{float(v or 0):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_danfe(xml_assinado: str, nfe: NotaFiscal, empresa: Empresa) -> str:
    """DANFE simplificado (retrato). Layout reduzido comparado a um DANFE
    oficial completo (não inclui todos os campos de canhoto/reservado ao
    fisco) — suficiente para conferência visual, não substitui geração via
    uma lib de DANFE dedicada para produção real."""
    root = etree.fromstring(xml_assinado.encode("utf-8"))
    ns = {"n": NFE_NS}

    def _get(path):
        el = root.find(path, ns)
        return el.text if el is not None else None

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    w = doc.width
    story = []

    # Cabeçalho
    logo_cell = Paragraph("", _D_N)
    if empresa.logo_path and os.path.exists(empresa.logo_path):
        try:
            from reportlab.platypus import Image as RLImage

            logo_cell = RLImage(empresa.logo_path, width=32 * mm, height=20 * mm)
        except Exception:
            pass

    emit_lines = [
        Paragraph(empresa.razao_social or "", _D_B),
        Paragraph(f"CNPJ: {empresa.cnpj or '-'}  IE: {empresa.ie or '-'}", _D_N),
        Paragraph(
            f"{empresa.endereco or ''}, {empresa.endereco_numero or ''} - {empresa.cidade or ''}/{empresa.uf_emitente}",
            _D_N,
        ),
    ]
    nfe_lines = [
        Paragraph("DANFE", _D_TITULO),
        Paragraph(f"NF-e Nº {nfe.numero}  Série {nfe.serie}", _D_B),
        Paragraph(f"Emissão: {nfe.data_emissao.strftime('%d/%m/%Y')}", _D_N),
        Paragraph("HOMOLOGAÇÃO" if empresa.ambiente_sefaz == "Homologacao" else "PRODUÇÃO", _D_B),
    ]
    hdr = Table([[logo_cell, emit_lines, nfe_lines]], colWidths=[w * 0.25, w * 0.45, w * 0.30])
    hdr.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                ("LINEAFTER", (0, 0), (1, 0), 0.4, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(hdr)
    story.append(Spacer(1, 3 * mm))

    # Chave de acesso + código de barras
    chave = nfe.chave_acesso or ""
    barcode = Code128(chave, barHeight=12 * mm, barWidth=0.3)
    story.append(barcode)
    story.append(Paragraph(f"Chave de acesso: {chave}", _D_CAP))
    story.append(Spacer(1, 3 * mm))

    # Destinatário
    dest_nome = _get(".//n:dest/n:xNome") or "-"
    dest_doc = _get(".//n:dest/n:CNPJ") or _get(".//n:dest/n:CPF") or "-"
    dest_end = _get(".//n:dest/n:enderDest/n:xLgr") or ""
    dest_mun = _get(".//n:dest/n:enderDest/n:xMun") or ""
    dest_uf = _get(".//n:dest/n:enderDest/n:UF") or ""
    story.append(Paragraph(f"<b>Destinatário:</b> {dest_nome}  —  CPF/CNPJ: {dest_doc}", _D_N))
    story.append(Paragraph(f"{dest_end} — {dest_mun}/{dest_uf}", _D_N))
    story.append(Spacer(1, 3 * mm))

    # Itens
    rows = [[Paragraph(h, _D_HDR) for h in ["Código", "Descrição", "NCM", "CFOP", "Qtd", "Un", "V.Unit", "V.Total"]]]
    for det in root.findall(".//n:det", ns):
        prod = det.find("n:prod", ns)

        def _p(tag, prod=prod):
            el = prod.find(f"n:{tag}", ns)
            return el.text if el is not None else ""

        rows.append(
            [
                Paragraph(_p("cProd"), _D_N),
                Paragraph(_p("xProd"), _D_N),
                Paragraph(_p("NCM"), _D_N),
                Paragraph(_p("CFOP"), _D_N),
                Paragraph(_p("qCom"), _D_N),
                Paragraph(_p("uCom"), _D_N),
                Paragraph(_brl(_p("vUnCom")), _D_N),
                Paragraph(_brl(_p("vProd")), _D_N),
            ]
        )
    col_w = [w * 0.10, w * 0.30, w * 0.10, w * 0.08, w * 0.10, w * 0.08, w * 0.12, w * 0.12]
    itens_t = Table(rows, colWidths=col_w, repeatRows=1)
    itens_t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.2, 0.2, 0.2)),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.Color(0.8, 0.8, 0.8)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(itens_t)
    story.append(Spacer(1, 3 * mm))

    # Totais
    v_prod = _get(".//n:total/n:ICMSTot/n:vProd") or "0.00"
    v_desc = _get(".//n:total/n:ICMSTot/n:vDesc") or "0.00"
    v_frete = _get(".//n:total/n:ICMSTot/n:vFrete") or "0.00"
    v_nf = _get(".//n:total/n:ICMSTot/n:vNF") or "0.00"
    tot = Table(
        [
            [
                Paragraph(f"Produtos: {_brl(v_prod)}", _D_N),
                Paragraph(f"Frete: {_brl(v_frete)}", _D_N),
                Paragraph(f"Desconto: {_brl(v_desc)}", _D_N),
                Paragraph(f"<b>TOTAL: {_brl(v_nf)}</b>", _D_B),
            ]
        ],
        colWidths=[w * 0.25] * 4,
    )
    tot.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.Color(0.96, 0.96, 0.96)),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(tot)
    story.append(Spacer(1, 3 * mm))

    inf_cpl = _get(".//n:infAdic/n:infCpl")
    if inf_cpl:
        story.append(Paragraph(f"<b>Informações adicionais:</b> {inf_cpl}", _D_N))
        story.append(Spacer(1, 2 * mm))

    story.append(Paragraph("Documento Auxiliar da Nota Fiscal Eletrônica", _D_CAP))

    doc.build(story)

    caminho = os.path.join(_NFE_BASE, "Geradas", f"{chave}.pdf")
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "wb") as f:
        f.write(buf.getvalue())
    return caminho


# ─────────────────────────────────────────────────────────────────────────
# LIMITAÇÕES CONHECIDAS (ver relatório final da conversa para o resumo):
#
# - montar_xml_nfe usa lxml puro em vez das dataclasses do nfelib: a API
#   tipada do nfelib é grande e arriscada de acertar de memória sem testar
#   contra homologação real; lxml dá controle explícito da ordem dos
#   elementos, que o XSD da NF-e exige rigidamente.
# - Grupo <pag> (forma de pagamento) é obrigatório no schema NF-e 4.00 e
#   NÃO foi incluído aqui — a especificação deste prompt não o pediu.
#   Sem ele, o XML será rejeitado por validação de schema na SEFAZ real.
# - PedidoVenda não tem campo de CPF separado do CNPJ (só cliente_cnpj) —
#   o tipo de documento do destinatário (CPF x CNPJ) é decidido por
#   contagem de dígitos (11 = CPF, 14 = CNPJ) até esse campo existir.
# - _mod11_dv não pôde ser validado contra uma chave de acesso real de
#   referência neste ambiente — revisar contra a SEFAZ homologação antes
#   de transmitir de verdade.
# - transmitir_nfe não pôde ser testada de ponta a ponta (sem certificado
#   real); a construção do client zeep com mTLS foi verificada
#   estruturalmente, não o round-trip autenticado completo.
# - montar_evento_cancelamento/montar_evento_cce montam e ASSINAM o XML do
#   evento localmente, mas não há uma função de transmissão para o
#   webservice de eventos (RecepcaoEvento) — é um endpoint SOAP diferente
#   do NFeAutorizacao4 usado em transmitir_nfe, não coberto pela FUNÇÃO 5
#   original. O router salva o evento assinado em disco e marca o status
#   localmente; a confirmação real do cancelamento/CC-e junto à SEFAZ
#   ficaria pendente de uma FUNÇÃO 7 (fora do escopo deste prompt).
# ─────────────────────────────────────────────────────────────────────────
