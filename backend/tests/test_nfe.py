"""Testes do módulo fiscal (Parte 8.1 — item 4).

Cobre: montagem do XML da NF-e a partir de pedido+empresa (estrutura,
chave de acesso com o dígito verificador módulo 11, totais), a assinatura
digital com um certificado self-signed de teste (perfil RSA-SHA1 exigido
pela SEFAZ), a transmissão com o zeep mockado (sem rede) e os eventos de
cancelamento/carta de correção (validação de tamanho + assinatura).
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest import mock

import pytest
from lxml import etree

from config import settings
from models.cliente import Cliente
from models.nfe import NotaFiscal
from models.pedido import ItemPedido, PedidoVenda
from models.produto import GrupoProduto, Produto
from models.tes import TES
from models.venda import Empresa
from services import nfe_service
from services.segredo_service import cifrar_segredo
from services.nfe_service import NFE_NS, _mod11_dv, montar_chave_acesso

_SENHA_CERT = "senha123"
_CHAVE_AES = "a" * 64  # 32 bytes em hex — chave de cifragem dos testes


# ── Certificado self-signed (apenas para testes) ────────────────────────


def _gerar_pfx_teste(caminho: Path, senha: str = _SENHA_CERT) -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "SMARTCUT TESTE LTDA")])
    agora = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(days=1))
        .not_valid_after(agora + timedelta(days=365))
        # cryptography >= 45 não assina mais certificado com SHA1 — usa SHA256
        # no certificado de teste (o XMLDSig da NF-e continua RSA-SHA1, que é
        # um caminho separado no signxml).
        .sign(key, hashes.SHA256())
    )
    dados = pkcs12.serialize_key_and_certificates(
        b"smartcut-teste",
        key,
        cert,
        None,
        serialization.BestAvailableEncryption(senha.encode("utf-8")),
    )
    caminho.write_bytes(dados)


@pytest.fixture()
def certificado(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "cert_senha_key", _CHAVE_AES)
    pfx = tmp_path / "certificado.pfx"
    _gerar_pfx_teste(pfx)
    return pfx


# ── Cenário mínimo (empresa + pedido + item com produto/TES) ────────────


@pytest.fixture()
def empresa(db_session):
    emp = Empresa(
        razao_social="SMARTCUT TESTE LTDA",
        cnpj="12345678000190",
        ie="1110000001",
        endereco="RUA DO TESTE",
        endereco_numero="100",
        endereco_bairro="CENTRO",
        codigo_ibge_municipio="4305108",
        cidade="CAXIAS DO SUL",
        cep="95000000",
        uf_emitente="RS",
        ambiente_sefaz="Homologacao",
        nfe_serie_padrao="001",
        nfe_numero_atual=0,
    )
    db_session.add(emp)
    db_session.commit()
    return emp


@pytest.fixture()
def produto(db_session):
    grupo = GrupoProduto(codigo="G01", nome="GRUPO TESTE", prefixo="GT")
    db_session.add(grupo)
    db_session.commit()
    p = Produto(
        grupo_id=grupo.id,
        codigo="P001",
        descricao="PRODUTO TESTE",
        unidade="UN",
        ncm="61091000",
        cod_barras="7890000000001",
        origem=0,
    )
    db_session.add(p)
    db_session.commit()
    return p


@pytest.fixture()
def tes(db_session):
    t = TES(
        codigo="5102",
        descricao="VENDA DE MERCADORIA",
        tipo="Saída",
        natureza_operacao="VENDA DE MERCADORIA",
        cfop="5102",
        csosn="102",
        origem="0",
        modalidade_bc_icms="3",
        pis_cst="49",
        cofins_cst="49",
    )
    db_session.add(t)
    db_session.commit()
    return t


@pytest.fixture()
def pedido_nfe(db_session, produto, tes):
    cliente = Cliente(
        codigo="0001",
        tipo_registro="cliente",
        tipo_pessoa="juridica",
        razao_social="CLIENTE LTDA",
        cnpj="12345678000190",
        endereco="RUA DO CLIENTE",
        numero="5",
        bairro="CENTRO",
        cidade="CAXIAS DO SUL",
        estado="RS",
        cep="95000000",
        codigo_ibge_municipio="4305108",
        codigo_pais="1058",
    )
    pedido = PedidoVenda(
        numero="000001",
        tipo="venda",
        data_emissao=date(2026, 9, 10),
        status="Aberto",
        condicoes="avista",
        cliente_id=cliente.id,
        cliente_razao_social=cliente.razao_social,
        cliente_cnpj=cliente.cnpj,
        cliente_ie=cliente.ie,
        cliente_endereco=cliente.endereco,
        cliente_numero=cliente.numero,
        cliente_bairro=cliente.bairro,
        cliente_cidade=cliente.cidade,
        cliente_uf=cliente.estado,
        cliente_cep=cliente.cep,
        cliente_codigo_ibge_municipio=cliente.codigo_ibge_municipio,
        cliente_codigo_pais=cliente.codigo_pais,
        cliente_telefone=cliente.telefone,
        indicador_presenca="Presencial",
        tipo_frete=None,
    )
    item = ItemPedido(
        pedido=pedido,
        produto_id=produto.id,
        tes_id=tes.id,
        qtd_m=2,
        preco_unitario=Decimal("150.00"),
        preco_total=Decimal("300.00"),
    )
    db_session.add_all([cliente, pedido, item])
    db_session.commit()
    return pedido


@pytest.fixture()
def nfe(db_session, pedido_nfe):
    nota = NotaFiscal(
        pedido_id=pedido_nfe.id,
        numero=1,
        serie="001",
        modelo="55",
        ambiente="Homologacao",
        data_emissao=datetime(2026, 9, 10, 10, 0, 0),
    )
    db_session.add(nota)
    db_session.commit()
    return nota


# ── Dígito verificador (módulo 11) ──────────────────────────────────────


def _dv_referencia(chave43: str) -> int:
    """Implementação de referência do DV módulo 11 (pesos 2..9 cíclicos,
    da direita para a esquerda) — independente do código sob teste."""
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = sum(int(c) * pesos[i % 8] for i, c in enumerate(reversed(chave43)))
    resto = soma % 11
    return 0 if resto in (0, 1) else 11 - resto


class TestDigitoVerificador:
    def test_dv_bate_com_referencia(self):
        for chave43 in ("43260911111111111111550010000000381602041", "35260614000155000033655010000000011234567"):
            assert _mod11_dv(chave43) == _dv_referencia(chave43)
            dv = _mod11_dv(chave43)
            assert isinstance(dv, int) and 0 <= dv <= 9

    def test_uma_alteracao_muda_o_dv(self):
        base = "43260911111111111111550010000000381602041"
        trocado = base[:-3] + str((int(base[-3]) + 1) % 10) + base[-2:]
        assert _mod11_dv(base) != _mod11_dv(trocado)

    def test_chave_montada_e_consistente(self, empresa, nfe):
        chave = montar_chave_acesso(empresa, nfe, "12345678")
        assert len(chave) == 44
        assert chave.isdigit()
        assert int(chave[-1]) == _mod11_dv(chave[:43])


# ── Montagem do XML ─────────────────────────────────────────────────────


class TestMontarXml:
    def test_estrutura_e_chave(self, empresa, pedido_nfe, nfe, db_session):
        xml = nfe_service.montar_xml_nfe(pedido_nfe, nfe, empresa, db_session)

        root = etree.fromstring(xml.encode("utf-8"))
        assert root.tag == f"{{{NFE_NS}}}NFe"
        inf = root.find(f"{{{NFE_NS}}}infNFe")
        assert inf.get("versao") == "4.00"
        assert inf.get("Id").startswith("NFe")
        assert len(nfe.chave_acesso) == 44
        assert inf.get("Id") == f"NFe{nfe.chave_acesso}"

    def test_ide_emit_dest(self, empresa, pedido_nfe, nfe, db_session):
        xml = nfe_service.montar_xml_nfe(pedido_nfe, nfe, empresa, db_session)
        root = etree.fromstring(xml.encode("utf-8"))
        ns = {"n": NFE_NS}

        assert root.find("n:infNFe/n:ide/n:cUF", ns).text == "43"
        assert root.find("n:infNFe/n:ide/n:mod", ns).text == "55"
        assert root.find("n:infNFe/n:ide/n:nNF", ns).text == "1"
        assert root.find("n:infNFe/n:ide/n:tpAmb", ns).text == "2"
        assert root.find("n:infNFe/n:ide/n:verProc", ns).text == "SmartCut 1.0"

        assert root.find("n:infNFe/n:emit/n:CNPJ", ns).text == "12345678000190"
        assert root.find("n:infNFe/n:emit/n:xNome", ns).text == "SMARTCUT TESTE LTDA"
        assert root.find("n:infNFe/n:emit/n:CRT", ns).text == "1"

        assert root.find("n:infNFe/n:dest/n:CNPJ", ns).text == "12345678000190"
        assert root.find("n:infNFe/n:dest/n:xNome", ns).text == "CLIENTE LTDA"
        assert root.find("n:infNFe/n:dest/n:indIEDest", ns).text == "9"

    def test_item_icms_e_totais(self, empresa, pedido_nfe, nfe, db_session):
        xml = nfe_service.montar_xml_nfe(pedido_nfe, nfe, empresa, db_session)
        root = etree.fromstring(xml.encode("utf-8"))
        ns = {"n": NFE_NS}

        det = root.find("n:infNFe/n:det", ns)
        assert det.get("nItem") == "1"
        prod = det.find("n:prod", ns)
        assert prod.find("n:cProd", ns).text == "P001"
        assert prod.find("n:xProd", ns).text == "PRODUTO TESTE"
        assert prod.find("n:NCM", ns).text == "61091000"
        assert prod.find("n:CFOP", ns).text == "5102"
        assert prod.find("n:qCom", ns).text == "2.0000"
        assert prod.find("n:vUnCom", ns).text == "150.00"
        assert prod.find("n:vProd", ns).text == "300.00"

        icms = det.find("n:imposto/n:ICMS/n:ICMSSN102", ns)
        assert icms is not None
        assert icms.find("n:orig", ns).text == "0"
        assert icms.find("n:CSOSN", ns).text == "102"

        tot = root.find("n:infNFe/n:total/n:ICMSTot", ns)
        assert tot.find("n:vProd", ns).text == "300.00"
        assert tot.find("n:vNF", ns).text == "300.00"
        assert float(nfe.valor_nf) == 300.00

    def test_pedido_sem_item_de_produto_recusa(self, empresa, nfe, db_session):
        pedido_vazio = PedidoVenda(
            numero="000002",
            tipo="venda",
            data_emissao=date(2026, 9, 10),
            status="Aberto",
        )
        db_session.add(pedido_vazio)
        db_session.commit()
        with pytest.raises(ValueError, match="produto_id"):
            nfe_service.montar_xml_nfe(pedido_vazio, nfe, empresa, db_session)


# ── Assinatura digital ──────────────────────────────────────────────────


class TestAssinatura:
    # Mesmo cenário montado via API de serviços (NFeXMLSigner + certificado).
    def test_assina_xml_com_self_signed(self, empresa, pedido_nfe, nfe, db_session, certificado):
        empresa.certificado_path = str(certificado)
        empresa.certificado_senha = cifrar_segredo(_SENHA_CERT)
        db_session.add(empresa)
        db_session.commit()

        xml = nfe_service.montar_xml_nfe(pedido_nfe, nfe, empresa, db_session)
        assinado = nfe_service.assinar_xml(xml, empresa)

        root = etree.fromstring(assinado.encode("utf-8"))
        ds = "http://www.w3.org/2000/09/xmldsig#"
        assert root.find(f".//{{{ds}}}Signature") is not None
        assert root.find(f"{{{NFE_NS}}}infNFe").get("Id").startswith("NFe")

    def test_sem_certificado_levanta_valorerror(self, empresa, pedido_nfe, nfe, db_session):
        xml = nfe_service.montar_xml_nfe(pedido_nfe, nfe, empresa, db_session)
        with pytest.raises(ValueError, match="Certificado digital não configurado"):
            nfe_service.assinar_xml(xml, empresa)


# ── Transmissão SEFAZ (zeep mockado) ────────────────────────────────────

_RESPOSTA_AUTORIZADA = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<nfeResultMsg xmlns="http://www.portalfiscal.inf.br/nfe">'
    '<retEnviNFe versao="4.00">'
    "<tpAmb>2</tpAmb><verAplic>RS20260910</verAplic>"
    "<cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo>"
    '<protNFe versao="4.00"><infProt>'
    "<tpAmb>2</tpAmb><verAplic>RS20260910</verAplic>"
    f"<chNFe>{'3' * 44}</chNFe>"
    "<dhRecbto>2026-09-10T10:00:00-03:00</dhRecbto>"
    "<nProt>143260000000001</nProt><digVal>YQ==</digVal>"
    "<cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo>"
    "</infProt></protNFe>"
    "</retEnviNFe>"
    "</nfeResultMsg>"
)


class TestTransmitir:
    def test_sem_certificado_levanta_valorerror(self, empresa):
        with pytest.raises(ValueError, match="Certificado digital não configurado"):
            nfe_service.transmitir_nfe("<NFe/>", empresa)

    def test_transmissao_autorizada_com_zeep_mockado(self, empresa, certificado):
        empresa.certificado_path = str(certificado)
        empresa.certificado_senha = cifrar_segredo(_SENHA_CERT)

        fake_client = mock.Mock()
        fake_client.service.nfeAutorizacaoLote.return_value = _RESPOSTA_AUTORIZADA

        with mock.patch("zeep.Client", return_value=fake_client) as cliente_mock:
            resultado = nfe_service.transmitir_nfe("<NFe/>", empresa)

        assert resultado["cStat"] == "100"
        assert resultado["xMotivo"] == "Autorizado o uso da NF-e"
        assert resultado["protocolo"] == "143260000000001"
        assert resultado["dhRecbto"].startswith("2026-09-10")
        assert cliente_mock.call_count == 1


# ── Eventos (cancelamento / carta de correção) ──────────────────────────


class TestEventos:
    def _empresa_com_cert(self, empresa, certificado):
        empresa.certificado_path = str(certificado)
        empresa.certificado_senha = cifrar_segredo(_SENHA_CERT)
        return empresa

    def test_cancelamento_curto_recusado(self, empresa, nfe):
        with pytest.raises(ValueError, match="mínimo 15"):
            nfe_service.montar_evento_cancelamento(empresa, nfe, "curto.")

    def test_cancelamento_monta_e_assina(self, empresa, nfe, certificado, db_session):
        empresa = self._empresa_com_cert(empresa, certificado)
        db_session.add(empresa)
        db_session.commit()
        nfe.chave_acesso = "3" * 44
        nfe.protocolo = "143260000000001"

        xml = nfe_service.montar_evento_cancelamento(empresa, nfe, "Cancelamento solicitado pelo emitente")
        root = etree.fromstring(xml.encode("utf-8"))
        inf = root.find(f"{{{NFE_NS}}}infEvento")
        assert inf.get("Id").startswith("ID110111")
        assert inf.find(f"{{{NFE_NS}}}tpEvento").text == "110111"
        assert inf.find(f"{{{NFE_NS}}}chNFe").text == nfe.chave_acesso
        assert inf.find(f"{{{NFE_NS}}}detEvento/{{{NFE_NS}}}xJust").text == "Cancelamento solicitado pelo emitente"
        ds = "http://www.w3.org/2000/09/xmldsig#"
        assert root.find(f".//{{{ds}}}Signature") is not None

    def test_cce_monta_e_assina(self, empresa, nfe, certificado, db_session):
        empresa = self._empresa_com_cert(empresa, certificado)
        db_session.add(empresa)
        db_session.commit()
        nfe.chave_acesso = "3" * 44

        xml = nfe_service.montar_evento_cce(empresa, nfe, "Correcao de endereco do destinatario")
        root = etree.fromstring(xml.encode("utf-8"))
        inf = root.find(f"{{{NFE_NS}}}infEvento")
        assert inf.find(f"{{{NFE_NS}}}tpEvento").text == "110110"
        assert inf.find(f"{{{NFE_NS}}}detEvento/{{{NFE_NS}}}xCorrecao") is not None
        assert inf.find(f"{{{NFE_NS}}}detEvento/{{{NFE_NS}}}xCondUso") is not None
        ds = "http://www.w3.org/2000/09/xmldsig#"
        assert root.find(f".//{{{ds}}}Signature") is not None


# ── Router (/api/v1/nfe) ────────────────────────────────────────────────


class TestRouterNFe:
    def test_listar_vazio(self, client, headers_admin):
        res = client.get("/api/v1/nfe/", headers=headers_admin)
        assert res.status_code == 200
        assert res.json()["data"] == []

    def test_listar_status_invalido_400(self, client, headers_admin):
        res = client.get("/api/v1/nfe/", headers=headers_admin, params={"status_filtro": "Inexistente"})
        assert res.status_code == 400
        assert "Status inválido" in res.json()["detail"]

    def test_listar_mes_invalido_400(self, client, headers_admin):
        res = client.get("/api/v1/nfe/", headers=headers_admin, params={"mes": "abc"})
        assert res.status_code == 400
        assert "mes" in res.json()["detail"]

    def test_obter_404(self, client, headers_admin):
        res = client.get("/api/v1/nfe/999999", headers=headers_admin)
        assert res.status_code == 404
        assert res.json()["detail"] == "NF-e não encontrada"

    def test_obter_e_listar_com_filtro(self, client, headers_admin, nfe):
        res = client.get(f"/api/v1/nfe/{nfe.id}", headers=headers_admin)
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["numero"] == nfe.numero
        assert data["status"] == "Rascunho"
        assert data["destinatario"] == "CLIENTE LTDA"

        res = client.get("/api/v1/nfe/", headers=headers_admin, params={"status_filtro": "Rascunho"})
        assert len(res.json()["data"]) == 1

    def test_transmitir_nao_rascunho_400(self, client, headers_admin, db_session, nfe):
        nfe.status = "Autorizada"
        db_session.commit()
        res = client.post(f"/api/v1/nfe/{nfe.id}/transmitir", headers=headers_admin)
        assert res.status_code == 400
        assert "não pode ser transmitida" in res.json()["detail"]

    def test_transmitir_sem_xml_400(self, client, headers_admin, nfe):
        res = client.post(f"/api/v1/nfe/{nfe.id}/transmitir", headers=headers_admin)
        assert res.status_code == 400
        assert "XML da NF-e não encontrado" in res.json()["detail"]

    def test_transmitir_autorizada_move_arquivo(self, client, headers_admin, db_session, monkeypatch, tmp_path, nfe):
        from routers import nfe as nfe_router

        geradas = tmp_path / "geradas"
        geradas.mkdir()
        arquivo = geradas / "chave.xml"
        arquivo.write_text("<NFe/>", encoding="utf-8")
        nfe.xml_path = str(arquivo)
        db_session.commit()
        enviadas = tmp_path / "enviadas"
        monkeypatch.setattr(nfe_router, "_XML_GERADAS", str(geradas))
        monkeypatch.setattr(nfe_router, "_XML_ENVIADAS", str(enviadas))

        with mock.patch.object(
            nfe_router,
            "transmitir_nfe",
            return_value={"cStat": "100", "protocolo": "143260000000001", "xMotivo": "Autorizado o uso da NF-e"},
        ):
            res = client.post(f"/api/v1/nfe/{nfe.id}/transmitir", headers=headers_admin)

        assert res.status_code == 200
        data = res.json()["data"]
        assert data["nfe"]["status"] == "Autorizada"
        assert data["nfe"]["protocolo"] == "143260000000001"
        assert data["resultado"]["cStat"] == "100"
        assert (enviadas / "chave.xml").exists()

    def test_transmitir_rejeitada_grava_motivo(self, client, headers_admin, db_session, monkeypatch, tmp_path, nfe):
        from routers import nfe as nfe_router

        geradas = tmp_path / "geradas2"
        geradas.mkdir()
        arquivo = geradas / "chave.xml"
        arquivo.write_text("<NFe/>", encoding="utf-8")
        nfe.xml_path = str(arquivo)
        db_session.commit()
        monkeypatch.setattr(nfe_router, "_XML_GERADAS", str(geradas))
        monkeypatch.setattr(nfe_router, "_XML_ENVIADAS", str(tmp_path / "enviadas2"))

        with mock.patch.object(
            nfe_router,
            "transmitir_nfe",
            return_value={"cStat": "110", "xMotivo": "Uso denegado - irregularidade fiscal do destinatário"},
        ):
            res = client.post(f"/api/v1/nfe/{nfe.id}/transmitir", headers=headers_admin)

        assert res.status_code == 200
        data = res.json()["data"]["nfe"]
        assert data["status"] == "Rejeitada"
        assert "irregularidade" in data["motivo_rejeicao"]

    def test_transmitir_falha_502(self, client, headers_admin, db_session, monkeypatch, tmp_path, nfe):
        from routers import nfe as nfe_router

        geradas = tmp_path / "geradas3"
        geradas.mkdir()
        arquivo = geradas / "chave.xml"
        arquivo.write_text("<NFe/>", encoding="utf-8")
        nfe.xml_path = str(arquivo)
        db_session.commit()
        monkeypatch.setattr(nfe_router, "_XML_GERADAS", str(geradas))

        with mock.patch.object(nfe_router, "transmitir_nfe", side_effect=RuntimeError("timeout na SEFAZ")):
            res = client.post(f"/api/v1/nfe/{nfe.id}/transmitir", headers=headers_admin)

        assert res.status_code == 502
        assert "SEFAZ" in res.json()["detail"]

    def test_cancelar_nao_autorizada_400(self, client, headers_admin, nfe):
        res = client.post(
            f"/api/v1/nfe/{nfe.id}/cancelar",
            headers=headers_admin,
            json={"justificativa": "Cancelamento solicitado pelo emitente"},
        )
        assert res.status_code == 400
        assert "Autorizada" in res.json()["detail"]

    def test_cancelar_autorizada_reabre_pedido(
        self, client, headers_admin, db_session, monkeypatch, tmp_path, nfe, pedido_nfe
    ):
        from routers import nfe as nfe_router

        nfe.status = "Autorizada"
        nfe.chave_acesso = "3" * 44
        nfe.data_autorizacao = datetime.now()
        pedido_nfe.nfe_id = nfe.id
        pedido_nfe.status = "Fechado"
        db_session.commit()
        pedido_id = pedido_nfe.id
        monkeypatch.setattr(nfe_router, "_XML_SOLIC_CANCELAMENTO", str(tmp_path / "canc"))

        with mock.patch.object(nfe_router, "montar_evento_cancelamento", return_value="<evento/>"):
            res = client.post(
                f"/api/v1/nfe/{nfe.id}/cancelar",
                headers=headers_admin,
                json={"justificativa": "Cancelamento solicitado pelo emitente"},
            )

        assert res.status_code == 200
        assert res.json()["data"]["status"] == "Cancelada"
        db_session.expire_all()  # sessão da requisição é separada — recarrega o pedido
        pedido = db_session.get(PedidoVenda, pedido_id)
        assert pedido.nfe_id is None
        assert pedido.status == "Aberto"

    def test_carta_correcao_nao_autorizada_400(self, client, headers_admin, nfe):
        res = client.post(
            f"/api/v1/nfe/{nfe.id}/carta-correcao",
            headers=headers_admin,
            json={"correcao": "Correcao de endereco do destinatario"},
        )
        assert res.status_code == 400
        assert "Autorizada" in res.json()["detail"]

    def test_carta_correcao_curta_422(self, client, headers_admin, nfe):
        res = client.post(
            f"/api/v1/nfe/{nfe.id}/carta-correcao",
            headers=headers_admin,
            json={"correcao": "curta"},
        )
        assert res.status_code == 422

    def test_carta_correcao_autorizada(self, client, headers_admin, db_session, monkeypatch, tmp_path, nfe):
        from routers import nfe as nfe_router

        nfe.status = "Autorizada"
        nfe.chave_acesso = "3" * 44
        db_session.commit()
        monkeypatch.setattr(nfe_router, "_XML_CARTAS_CORRECAO", str(tmp_path / "cce"))

        with mock.patch.object(nfe_router, "montar_evento_cce", return_value="<evento/>"):
            res = client.post(
                f"/api/v1/nfe/{nfe.id}/carta-correcao",
                headers=headers_admin,
                json={"correcao": "Correcao de endereco do destinatario"},
            )

        assert res.status_code == 200
        assert res.json()["data"]["carta_correcao"] == "Correcao de endereco do destinatario"

    def test_danfe_sem_xml_400(self, client, headers_admin, nfe):
        res = client.get(f"/api/v1/nfe/{nfe.id}/danfe", headers=headers_admin)
        assert res.status_code == 400
        assert "DANFE" in res.json()["detail"]

    def test_criar_nfe_vincula_e_fecha_pedido(
        self,
        client,
        headers_admin,
        db_session,
        monkeypatch,
        tmp_path,
        empresa,
        pedido_nfe,
        certificado,
    ):
        from routers import nfe as nfe_router

        empresa.certificado_path = str(certificado)
        empresa.certificado_senha = cifrar_segredo(_SENHA_CERT)
        db_session.add(empresa)
        db_session.commit()
        pedido_id = pedido_nfe.id
        geradas = tmp_path / "geradas"
        geradas.mkdir()  # criar_pastas_nfe é neutralizado no teste
        monkeypatch.setattr(nfe_router, "_XML_GERADAS", str(geradas))
        monkeypatch.setattr(nfe_router, "criar_pastas_nfe", lambda: None)

        res = client.post(
            "/api/v1/nfe/",
            headers=headers_admin,
            json={"pedido_id": str(pedido_id), "serie": "001", "data_emissao": "2026-09-10"},
        )

        assert res.status_code == 201, res.text
        data = res.json()["data"]
        assert data["status"] == "Rascunho"
        assert len(data["chave_acesso"]) == 44
        db_session.expire_all()  # sessão da requisição é separada — recarrega o pedido
        pedido = db_session.get(PedidoVenda, pedido_id)
        assert pedido.status == "Fechado"
        assert pedido.nfe_id == data["id"]

    def test_criar_nfe_pedido_ja_vinculado_400(
        self, client, headers_admin, db_session, monkeypatch, tmp_path, empresa, pedido_nfe, certificado
    ):
        from routers import nfe as nfe_router

        empresa.certificado_path = str(certificado)
        empresa.certificado_senha = cifrar_segredo(_SENHA_CERT)
        pedido_nfe.nfe_id = 999
        db_session.add(empresa)
        db_session.commit()
        monkeypatch.setattr(nfe_router, "_XML_GERADAS", str(tmp_path / "geradas"))
        monkeypatch.setattr(nfe_router, "criar_pastas_nfe", lambda: None)

        res = client.post(
            "/api/v1/nfe/",
            headers=headers_admin,
            json={"pedido_id": str(pedido_nfe.id), "serie": "001", "data_emissao": "2026-09-10"},
        )
        assert res.status_code == 400
        assert "já possui uma NF-e" in res.json()["detail"]
