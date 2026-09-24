"""Testes diretos dos parsers de arquivos (Parte 8.1 — item 3).

Complementa os testes HTTP de preview/import de moldes com recursos que
só aparecem em arquivos específicos: peças montadas a partir de LINE,
nomes sugeridos por texto próximo, detecção do sentido do fio, o laço
PE-encoding do HP-GL/2 e os caminhos de erro (arquivo inválido).
"""

import io

import ezdxf
import pytest

from parsers.dxf_parser import parse_dxf
from parsers.plt_parser import parse_plt


# ── Helpers de geração de arquivos ─────────────────────────────────────


def _dxf_bytes(polylines=(), lines=(), textos=()) -> bytes:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    for pts in polylines:
        msp.add_lwpolyline(pts, close=True)
    for a, b in lines:
        msp.add_line(a, b)
    for pos, texto in textos:
        msp.add_text(texto, height=1).set_placement(pos)
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def _arquivo(tmp_path, nome: str, dados: bytes) -> str:
    caminho = tmp_path / nome
    caminho.write_bytes(dados)
    return str(caminho)


def _pe_valor(v: int) -> bytes:
    """Codifica um inteiro no formato PE (zigzag + grupos LSB-first de 6 bits)."""
    zz = v << 1 if v >= 0 else ((-v << 1) - 1)
    grupos: list[int] = []
    while True:
        grupos.append(zz & 0x3F)
        zz >>= 6
        if zz == 0:
            break
    return b"".join(bytes([g + (191 if i == len(grupos) - 1 else 63)]) for i, g in enumerate(grupos))


def _pe_arquivo(coords_por_polyline: list[list[int]]) -> bytes:
    """Monta arquivo PLT PE: 'PE' + '<=' + coords codificadas por polyline."""
    partes = [b"PE"]
    for coords in coords_por_polyline:
        partes.append(b"<=")
        partes.append(b"".join(_pe_valor(c) for c in coords))
    return b"".join(partes)


# ── DXF ────────────────────────────────────────────────────────────────

QUADRADO = [(0, 0), (10, 0), (10, 10), (0, 10)]  # 10cm x 10cm → 100 cm²


class TestParseDXF:
    def test_lwpolyline_fechada_vira_peca(self, tmp_path):
        arquivo = _arquivo(tmp_path, "quadrado.dxf", _dxf_bytes(polylines=[QUADRADO]))
        pecas = parse_dxf(arquivo)
        assert len(pecas) == 1
        assert pecas[0]["area_cm2"] == 100.0
        assert pecas[0]["nome_sugerido"] == "Peça 1"
        assert pecas[0]["geometria_json"]["type"] == "Polygon"

    def test_line_fechada_monta_contorno(self, tmp_path):
        linhas = [
            ((0, 0), (10, 0)),
            ((10, 0), (10, 10)),
            ((10, 10), (0, 10)),
            ((0, 10), (0, 0)),
        ]
        arquivo = _arquivo(tmp_path, "contorno.dxf", _dxf_bytes(lines=linhas))
        pecas = parse_dxf(arquivo)
        assert len(pecas) == 1
        assert pecas[0]["area_cm2"] == 100.0

    def test_area_minima_ignora_poligono_pequeno(self, tmp_path):
        pequeno = [(0, 0), (0.5, 0), (0.5, 0.5), (0, 0.5)]  # 0.25 cm² < 1.0
        arquivo = _arquivo(tmp_path, "pequeno.dxf", _dxf_bytes(polylines=[pequeno]))
        assert parse_dxf(arquivo) == []

    def test_polyline_de_2_pontos_ignorada(self, tmp_path):
        arquivo = _arquivo(tmp_path, "2p.dxf", _dxf_bytes(polylines=[[(0, 0), (10, 0)]]))
        assert parse_dxf(arquivo) == []

    def test_texto_proximo_vira_nome_sugerido(self, tmp_path):
        arquivo = _arquivo(
            tmp_path,
            "frente.dxf",
            _dxf_bytes(polylines=[QUADRADO], textos=[((5, 5), "FRENTE")]),
        )
        pecas = parse_dxf(arquivo)
        assert len(pecas) == 1
        assert pecas[0]["nome_sugerido"] == "FRENTE"

    def test_texto_apenas_numero_ignorado(self, tmp_path):
        arquivo = _arquivo(
            tmp_path,
            "qtd.dxf",
            _dxf_bytes(polylines=[QUADRADO], textos=[((5, 5), "2 pares")]),
        )
        assert parse_dxf(arquivo)[0]["nome_sugerido"] == "Peça 1"

    def test_sentido_fio_horizontal_detectado(self, tmp_path):
        arquivo = _arquivo(
            tmp_path,
            "fio.dxf",
            _dxf_bytes(
                polylines=[QUADRADO],
                lines=[((0, 5), (10, 5)), ((1, 1), (2, 1)), ((1, 3), (2, 3))],
            ),
        )
        pecas = parse_dxf(arquivo)
        assert len(pecas) == 1
        assert pecas[0]["sentido_fio_detectado"] == "horizontal"

    def test_sem_linhas_o_sentido_fica_none(self, tmp_path):
        arquivo = _arquivo(tmp_path, "semfio.dxf", _dxf_bytes(polylines=[QUADRADO]))
        assert parse_dxf(arquivo)[0]["sentido_fio_detectado"] is None

    def test_arquivo_invalido_levanta_erro(self, tmp_path):
        arquivo = _arquivo(tmp_path, "lixo.dxf", b"\x00\x01conteudo sem estrutura dxf")
        with pytest.raises((ezdxf.DXFError, ValueError, OSError)):
            parse_dxf(arquivo)


# ── PLT ────────────────────────────────────────────────────────────────

QUADRADO_PE_COORDS = [0, 0, 4000, 0, 0, 4000, -4000, 0, 0, -4000]  # 4000 un = 10cm

PLT_TEXTUAL = "IN;PU;SP1;PU0,0;PD0,0,4000,0,4000,4000,0,4000,0,0;PU;"


class TestParsePLT:
    def test_pe_encoding_quadrado(self, tmp_path):
        arquivo = _arquivo(tmp_path, "quadrado.plt", _pe_arquivo([QUADRADO_PE_COORDS]))
        pecas = parse_plt(arquivo)
        assert len(pecas) == 1
        assert pecas[0]["area_cm2"] == 100.0
        assert pecas[0]["nome_sugerido"] == "Peça 1"

    def test_pe_aberta_e_pequena_ignoradas(self, tmp_path):
        aberta = [0, 0, 4000, 0, 0, 4000, -4000, 0]  # não fecha
        pequena = [0, 0, 1000, 0, 0, 1000, -1000, 0, 0, -1000]  # 2.5cm → 6.25 cm²
        arquivo = _arquivo(tmp_path, "varias.plt", _pe_arquivo([aberta, pequena]))
        assert parse_plt(arquivo) == []

    def test_pe_sem_marcador_retorna_vazio(self, tmp_path):
        arquivo = _arquivo(tmp_path, "vazio.plt", b"PE" + _pe_valor(4000))
        assert parse_plt(arquivo) == []

    def test_fallback_textual_quadrado(self, tmp_path):
        arquivo = _arquivo(tmp_path, "textual.plt", PLT_TEXTUAL.encode("latin-1"))
        pecas = parse_plt(arquivo)
        assert len(pecas) == 1
        assert pecas[0]["area_cm2"] == pytest.approx(100.0, abs=0.01)

    def test_decodificacao_zigzag_bate_com_referencia(self):
        # 4000 → zigzag 8000; -4000 → zigzag 7999. Decodifica de volta.
        assert _pe_valor(4000).decode("latin-1")  # só garante que gera bytes válidos
        dados = _pe_valor(4000) + _pe_valor(-4000)
        # Reutiliza o decodificador interno do parser (sem passar por arquivo).
        from parsers.plt_parser import _decode_coords

        coords = _decode_coords(dados)
        assert coords == [4000, -4000]
