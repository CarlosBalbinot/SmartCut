"""Arquivos do usuário na pasta de dados (fora da pasta de instalação).

A fixture autouse ``_pasta_dados_temporaria`` (conftest) aponta
SMARTCUT_DADOS_DIR para uma pasta temporária — aqui ela faz o papel do
``%APPDATA%\\smartcut`` do app instalado.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from config import settings
from models.financeiro import AnexoLancamento, Lancamento
from services import pasta_dados
from services.venda_service import _guardar_certificado


@pytest.fixture()
def lancamento(db_session):
    lanc = Lancamento(
        id=uuid.uuid4(),
        tipo="PAGAR",
        descricao="Teste",
        valor=Decimal("10.00"),
        data_vencimento=date(2026, 10, 1),
        status="PENDENTE",
    )
    db_session.add(lanc)
    db_session.commit()
    return lanc


def _enviar(client, headers, lanc_id, nome="nota.pdf", conteudo=b"%PDF-1"):
    return client.post(
        f"/api/financeiro/lancamentos/{lanc_id}/anexos",
        headers=headers,
        files={"arquivo": (nome, conteudo, "application/pdf")},
        data={"tipo": "NF"},
    )


class TestResolucao:
    def test_relativo_e_resolver(self, _pasta_dados_temporaria):
        base = _pasta_dados_temporaria
        assert pasta_dados.pasta_dados() == base.resolve()
        alvo = base / "uploads" / "financeiro" / "x.pdf"
        assert pasta_dados.relativo(alvo) == "uploads/financeiro/x.pdf"
        assert pasta_dados.resolver("uploads/financeiro/x.pdf") == base.resolve() / "uploads/financeiro/x.pdf"
        # gravações antigas com "\\" (moldes no Windows)
        assert pasta_dados.resolver("uploads\\a.dxf") == base.resolve() / "uploads" / "a.dxf"

    def test_absoluto_fora_da_pasta_fica_absoluto(self, tmp_path):
        fora = tmp_path / "outro" / "c.pfx"
        assert pasta_dados.resolver(str(fora)) == fora
        assert pasta_dados.relativo(fora) == str(fora.resolve())

    def test_dev_sem_variavel_usa_backend(self, monkeypatch):
        monkeypatch.setattr(settings, "smartcut_dados_dir", "")
        from pathlib import Path

        assert pasta_dados.pasta_dados() == Path(pasta_dados.__file__).resolve().parents[1]


class TestAnexos:
    def test_upload_grava_na_pasta_de_dados_com_caminho_relativo(
        self, client, headers_admin, lancamento, _pasta_dados_temporaria
    ):
        res = _enviar(client, headers_admin, lancamento.id)
        assert res.status_code == 200, res.text
        anexo = res.json()["data"]
        assert anexo["arquivo_path"].startswith(f"uploads/financeiro/{lancamento.id}/")
        assert anexo["arquivo_existe"] is True
        assert (_pasta_dados_temporaria / anexo["arquivo_path"]).read_bytes() == b"%PDF-1"

        baixado = client.get(f"/api/financeiro/anexos/{anexo['id']}/download", headers=headers_admin)
        assert baixado.status_code == 200
        assert baixado.content == b"%PDF-1"

    def test_arquivo_perdido_e_reenvio(self, client, headers_admin, lancamento, _pasta_dados_temporaria):
        anexo = _enviar(client, headers_admin, lancamento.id).json()["data"]
        (_pasta_dados_temporaria / anexo["arquivo_path"]).unlink()

        lista = client.get(f"/api/financeiro/lancamentos/{lancamento.id}/anexos", headers=headers_admin)
        assert lista.json()["data"][0]["arquivo_existe"] is False
        baixado = client.get(f"/api/financeiro/anexos/{anexo['id']}/download", headers=headers_admin)
        assert baixado.status_code == 404
        assert baixado.json()["detail"] == "Arquivo não encontrado"

        res = client.put(
            f"/api/financeiro/anexos/{anexo['id']}/arquivo",
            headers=headers_admin,
            files={"arquivo": ("nova.pdf", b"%PDF-2", "application/pdf")},
        )
        assert res.status_code == 200, res.text
        novo = res.json()["data"]
        assert novo["id"] == anexo["id"]
        assert novo["tipo"] == "NF"
        assert novo["nome_original"] == "nova.pdf"
        assert novo["arquivo_existe"] is True
        assert (_pasta_dados_temporaria / novo["arquivo_path"]).read_bytes() == b"%PDF-2"

    def test_excluir_remove_arquivo(self, client, headers_admin, lancamento, _pasta_dados_temporaria, db_session):
        anexo = _enviar(client, headers_admin, lancamento.id).json()["data"]
        arquivo = _pasta_dados_temporaria / anexo["arquivo_path"]
        assert client.delete(f"/api/financeiro/anexos/{anexo['id']}", headers=headers_admin).status_code == 200
        assert not arquivo.exists()
        assert db_session.get(AnexoLancamento, uuid.UUID(anexo["id"])) is None


class TestLogoECertificado:
    def test_logo_na_pasta_de_dados(self, client, headers_admin, _pasta_dados_temporaria):
        res = client.patch(
            "/api/v1/configuracao-empresa/logo",
            headers=headers_admin,
            files={"logo": ("logo.png", b"PNG", "image/png")},
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["logo_path"] == "uploads/logos/empresa_logo.png"
        assert (_pasta_dados_temporaria / "uploads/logos/empresa_logo.png").read_bytes() == b"PNG"
        assert client.get("/api/v1/configuracao-empresa/logo").content == b"PNG"

    def test_certificado_copiado_para_pasta_de_dados(self, tmp_path, _pasta_dados_temporaria):
        origem = tmp_path / "downloads" / "empresa.pfx"
        origem.parent.mkdir()
        origem.write_bytes(b"PFX")
        gravado = _guardar_certificado(str(origem))
        assert gravado == "Certificados/empresa.pfx"
        assert (_pasta_dados_temporaria / gravado).read_bytes() == b"PFX"
        # salvar de novo com o caminho já relativo não duplica nem quebra
        assert _guardar_certificado(gravado) == gravado
