"""Testes de clientes (CRUD) e moldes (CRUD + importação DXF/PLT/ADS)
(Parte 8.1 — cadastros).

As fixtures de arquivo são mínimas mas válidas para cada parser:
- DXF:  LWPOLYLINE fechada 10×10 → peça única de 100 cm²;
- PLT:  HPGL textual com PU/PD (sem marcador PE) → quadrado 400×400 un. = 1 cm²;
- ADS:  cabeçalho CADZ + miniatura JPEG + 4 segmentos count=4 → peça de 100 cm²
        (faixa aceita pelo parser: 20–30000 cm²).
"""

import struct

import pytest

from config import settings


def _dxf_minimo_bytes() -> bytes:
    """Gera a LWPOLYLINE via ezdxf — o marcador de subclasse (100/AcDbPolyline)
    é obrigatório e fácil de errar escrevendo o DXF à mão."""
    import io

    import ezdxf

    doc = ezdxf.new("R2010")
    doc.modelspace().add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True)
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


PLT_TEXTUAL = b"IN;PU;PD0,0;PD0,400;PD400,400;PD400,0;PD0,0;PU;SP1;"


def _ads_minimo() -> bytes:
    """Quadrado 10×10 cm (área 100 cm²) no formato binário CADZ."""

    def rec(n, *valores):
        return struct.pack("<I", n) + struct.pack(f"<{n}d", *valores)

    cabecalho = b"CADZ vs5.0" + b"\x00\x00"  # 12 bytes antes do JPEG
    jpeg = b"\xff\xd8" + b"\x00\x01\x02" + b"\xff\xd9"  # miniatura dummy
    segmentos = b"".join(
        [
            rec(4, 0, 0, 0, 10),
            rec(4, 0, 10, 10, 10),
            rec(4, 10, 10, 10, 0),
            rec(4, 10, 0, 0, 0),
        ]
    )
    return cabecalho + jpeg + segmentos


@pytest.fixture()
def upload_dir(tmp_path, monkeypatch):
    """O preview escreve em settings.upload_dir — aponta para o tmp do teste."""
    d = tmp_path / "uploads"
    d.mkdir()
    monkeypatch.setattr(settings, "upload_dir", str(d))
    return d


class TestClientesCRUD:
    def _criar(self, client, headers_admin):
        res = client.post(
            "/api/v1/clientes/",
            headers=headers_admin,
            json={
                "tipo_registro": "cliente",
                "tipo_pessoa": "juridica",
                "razao_social": "EMPRESA TESTE LTDA",
                "cnpj": "12345678000190",
                "cidade": "CAXIAS DO SUL",
                "estado": "RS",
            },
        )
        assert res.status_code == 201, res.text
        return res.json()["data"]

    def test_criar_listar_obter_atualizar_e_inativar(self, client, headers_admin):
        created = self._criar(client, headers_admin)
        assert created["codigo"] == "0001"
        assert created["razao_social"] == "EMPRESA TESTE LTDA"

        lista = client.get("/api/v1/clientes/", headers=headers_admin).json()["data"]
        assert len(lista) == 1

        obtido = client.get(f"/api/v1/clientes/{created['id']}", headers=headers_admin).json()["data"]
        assert obtido["cnpj"] == "12345678000190"

        atualizado = client.put(
            f"/api/v1/clientes/{created['id']}",
            headers=headers_admin,
            json={"nome_fantasia": "EMPRESA FANTASIA"},
        )
        assert atualizado.status_code == 200, atualizado.text
        data = atualizado.json()["data"]
        assert data["nome_fantasia"] == "EMPRESA FANTASIA"
        assert data["pedidos_sincronizados"] == 0

        # DELETE é inativação (soft delete) — regra já existente.
        res = client.delete(f"/api/v1/clientes/{created['id']}", headers=headers_admin)
        assert res.status_code == 200
        assert res.json()["data"] == {"excluido": True}
        obtido = client.get(f"/api/v1/clientes/{created['id']}", headers=headers_admin).json()["data"]
        assert obtido["ativo"] is False

    def test_codigo_incrementa(self, client, headers_admin):
        c1 = self._criar(client, headers_admin)
        c2 = self._criar(client, headers_admin)
        assert (c1["codigo"], c2["codigo"]) == ("0001", "0002")

    def test_lookup_por_codigo_ou_cnpj(self, client, headers_admin):
        c = self._criar(client, headers_admin)
        # Por CNPJ (14 dígitos → documento)
        res = client.get("/api/v1/clientes/validar", headers=headers_admin, params={"codigo": "12345678000190"})
        assert res.status_code == 200, res.text
        assert res.json()["data"]["id"] == c["id"]
        # Por código "1" também acha "0001"
        res = client.get("/api/v1/clientes/validar", headers=headers_admin, params={"codigo": "1"})
        assert res.status_code == 200
        assert res.json()["data"]["id"] == c["id"]

    def test_sem_permissao_403(self, client, usuario_simples):
        from services.auth_service import criar_token_admin

        token = criar_token_admin(usuario_simples)
        res = client.get("/api/v1/clientes/", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403


class TestPreviewImportacao:
    def _preview(self, client, headers_admin, nome, conteudo):
        res = client.post(
            "/api/v1/moldes/preview",
            headers=headers_admin,
            files={"arquivo": (nome, conteudo, "application/octet-stream")},
        )
        assert res.status_code == 200, res.text
        return res.json()["data"]

    def test_dxf(self, client, headers_admin, upload_dir):
        data = self._preview(client, headers_admin, "peca.dxf", _dxf_minimo_bytes())
        assert data["formato"] == "DXF"
        assert len(data["pecas"]) == 1
        assert data["pecas"][0]["area_cm2"] == 100.0

    def test_plt(self, client, headers_admin, upload_dir):
        data = self._preview(client, headers_admin, "peca.plt", PLT_TEXTUAL)
        assert data["formato"] == "PLT"
        assert len(data["pecas"]) == 1

    def test_ads(self, client, headers_admin, upload_dir):
        data = self._preview(client, headers_admin, "peca.ads", _ads_minimo())
        assert data["formato"] == "ADS"
        assert len(data["pecas"]) == 1

    def test_formato_nao_suportado_422(self, client, headers_admin, upload_dir):
        res = client.post(
            "/api/v1/moldes/preview",
            headers=headers_admin,
            files={"arquivo": ("peca.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert res.status_code == 422
        assert "não suportado" in res.json()["detail"]


class TestMoldesCRUD:
    def _importar(self, client, headers_admin, upload_dir):
        preview = self._preview(client, headers_admin, "peca.dxf", _dxf_minimo_bytes())
        peca = preview["pecas"][0]
        res = client.post(
            "/api/v1/moldes/bulk",
            headers=headers_admin,
            json={
                "arquivo_path": preview["arquivo_path"],
                "formato": "DXF",
                "pecas": [
                    {
                        "nome": "FRENTE",
                        "peca": "Frente",
                        "tamanho": "M",
                        "tipo_corte": "simples",
                        "rotacao_base": 0,
                        "geometria_json": peca["geometria_json"],
                        "area_cm2": peca["area_cm2"],
                    }
                ],
            },
        )
        assert res.status_code == 201, res.text
        return res.json()["data"]

    def _preview(self, client, headers_admin, nome, conteudo):
        res = client.post(
            "/api/v1/moldes/preview",
            headers=headers_admin,
            files={"arquivo": (nome, conteudo, "application/octet-stream")},
        )
        assert res.status_code == 200, res.text
        return res.json()["data"]

    def test_importar_atualizar_listar_e_deletar(self, client, headers_admin, upload_dir):
        criados = self._importar(client, headers_admin, upload_dir)
        assert len(criados) == 1
        molde_id = criados[0]["id"]
        assert criados[0]["nome"] == "FRENTE"
        assert criados[0]["formato"] == "DXF"

        lista = client.get("/api/v1/moldes/", headers=headers_admin).json()["data"]
        assert len(lista) == 1

        obtido = client.get(f"/api/v1/moldes/{molde_id}", headers=headers_admin).json()["data"]
        assert obtido["tamanho"] == "M"

        upd = client.patch(
            f"/api/v1/moldes/{molde_id}",
            headers=headers_admin,
            json={"nome": "FRENTE M", "tipo_corte": "par"},
        )
        assert upd.status_code == 200, upd.text
        assert upd.json()["data"]["nome"] == "FRENTE M"
        assert upd.json()["data"]["tipo_corte"] == "par"

        res = client.delete(f"/api/v1/moldes/{molde_id}", headers=headers_admin)
        assert res.status_code == 200
        assert res.json()["data"] == {"deleted": True}
        assert client.get(f"/api/v1/moldes/{molde_id}", headers=headers_admin).status_code == 404

    def test_tipo_corte_e_obrigatorio(self, client, headers_admin, upload_dir):
        # O tipo de corte diz quantas peças físicas saem de um molde (1 ou 2) e
        # se a segunda sai espelhada. Sem default, a API não aceita omissão —
        # o antigo default "par" do import em grupo dobrava a produção de peça
        # sem ninguém pedir.
        preview = self._preview(client, headers_admin, "peca.dxf", _dxf_minimo_bytes())
        peca = preview["pecas"][0]
        base = {
            "nome": "FRENTE",
            "peca": "Frente",
            "tamanho": "M",
            "rotacao_base": 0,
            "geometria_json": peca["geometria_json"],
            "area_cm2": peca["area_cm2"],
        }

        res = client.post(
            "/api/v1/moldes/bulk",
            headers=headers_admin,
            json={
                "arquivo_path": preview["arquivo_path"],
                "formato": "DXF",
                "pecas": [base],  # sem tipo_corte
            },
        )
        assert res.status_code == 422, res.text

        # e o mesmo na importação em grupo
        res = client.post(
            "/api/v1/grupos-molde/importar",
            headers=headers_admin,
            json={
                "nome_grupo": "LEGGING",
                "arquivo_path": preview["arquivo_path"],
                "formato": "DXF",
                "partes": [
                    {
                        "nome": "COSTAS",
                        "sentido_fio": "vertical",
                        "rotacao_base": 0,
                        "pecas": [
                            {
                                "tamanho": "M",
                                "geometria_json": peca["geometria_json"],
                                "area_cm2": peca["area_cm2"],
                            }
                        ],
                    }
                ],
            },
        )
        assert res.status_code == 422, res.text

        # com o valor escolhido, passa
        res = client.post(
            "/api/v1/grupos-molde/importar",
            headers=headers_admin,
            json={
                "nome_grupo": "LEGGING",
                "arquivo_path": preview["arquivo_path"],
                "formato": "DXF",
                "partes": [
                    {
                        "nome": "COSTAS",
                        "tipo_corte": "par",
                        "sentido_fio": "vertical",
                        "rotacao_base": 0,
                        "pecas": [
                            {
                                "tamanho": "M",
                                "geometria_json": peca["geometria_json"],
                                "area_cm2": peca["area_cm2"],
                            }
                        ],
                    }
                ],
            },
        )
        assert res.status_code == 201, res.text
