"""scripts/montar_banco_producao.py: arquivos na estrutura da pasta de dados,
anexo sem arquivo descartado (com contagem no relatório) e validações."""

import shutil
import sqlite3
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models.financeiro import AnexoLancamento, ContaBancaria, Lancamento, SaldoInicialConta
from models.molde import Molde
from models.precificacao import ConfiguracaoEmpresa
from models.venda import Empresa
from scripts.montar_banco_producao import montar
from services.db_migracoes import aplicar_migracoes


def _banco(caminho, modelo):
    shutil.copy2(modelo, caminho)
    return create_engine(f"sqlite:///{caminho}")


def test_monta_pasta_de_dados_e_descarta_anexo_sem_arquivo(tmp_path):
    modelo = tmp_path / "modelo.db"
    aplicar_migracoes(f"sqlite:///{modelo}")

    # Instalado: 1 conta, 1 lançamento pago, 2 anexos (só um tem arquivo).
    base_inst = tmp_path / "bin"
    lanc_id = uuid.uuid4()
    existente = f"uploads/financeiro/{lanc_id}/ok.pdf"
    (base_inst / existente).parent.mkdir(parents=True)
    (base_inst / existente).write_bytes(b"PDF")
    eng = _banco(tmp_path / "instalado.db", modelo)
    with Session(eng) as s:
        conta = ContaBancaria(nome="CAIXA", tipo="CAIXA")
        s.add(conta)
        s.flush()
        s.add(SaldoInicialConta(conta_bancaria_id=conta.id, mes=9, ano=2026, valor=Decimal("100.00")))
        s.add(
            Lancamento(
                id=lanc_id,
                tipo="RECEBER",
                descricao="VENDA",
                valor=Decimal("50.00"),
                data_vencimento=date(2026, 9, 10),
                data_pagamento=date(2026, 9, 10),
                status="PAGO",
                conta_bancaria_id=conta.id,
            )
        )
        s.flush()
        s.add(AnexoLancamento(lancamento_id=lanc_id, arquivo_path=existente, tipo="NF", nome_original="ok.pdf"))
        s.add(
            AnexoLancamento(
                lancamento_id=lanc_id,
                arquivo_path=f"uploads/financeiro/{lanc_id}/perdido.pdf",
                tipo="BOLETO",
                nome_original="perdido.pdf",
            )
        )
        s.commit()
    eng.dispose()

    # Dev: empresa com logo, molde gravado com "\\" (Windows), configuração.
    base_dev = tmp_path / "backend"
    (base_dev / "uploads" / "logos").mkdir(parents=True)
    (base_dev / "uploads" / "logos" / "empresa_logo.png").write_bytes(b"PNG")
    (base_dev / "uploads" / "a.dxf").write_bytes(b"DXF")
    eng = _banco(tmp_path / "dev.db", modelo)
    with Session(eng) as s:
        s.add(Empresa(logo_path="uploads/logos/empresa_logo.png"))
        s.add(ConfiguracaoEmpresa())
        s.add(Molde(nome="FRENTE", arquivo_path="uploads\\a.dxf", tipo_corte="simples"))
        s.commit()
    eng.dispose()

    saida = tmp_path / "saida"
    assert montar(tmp_path / "instalado.db", tmp_path / "dev.db", base_inst, base_dev, saida) == 0

    assert (saida / existente).read_bytes() == b"PDF"
    assert (saida / "uploads/logos/empresa_logo.png").read_bytes() == b"PNG"
    assert (saida / "uploads/a.dxf").read_bytes() == b"DXF"
    con = sqlite3.connect(saida / "smartcut.db")
    assert con.execute("select arquivo_path from anexos_lancamento").fetchall() == [(existente,)]
    assert con.execute("select arquivo_path from moldes").fetchall() == [("uploads/a.dxf",)]
    assert con.execute("select count(*) from lancamentos").fetchone() == (1,)
    con.close()

    relatorio = (saida / "relatorio_montagem.txt").read_text(encoding="utf-8")
    assert "Anexos descartados por arquivo inexistente: 1" in relatorio
    assert "5. Saldos por conta" in relatorio
    assert "<-- DIFERENTE" not in relatorio
    assert "RESULTADO: OK (1 anexo(s) descartado(s) por arquivo inexistente)" in relatorio
