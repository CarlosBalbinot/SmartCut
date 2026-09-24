"""Popula as tabelas de grade padrão (COR e TAMANHO).

Uso: py -3.12 -m scripts.seed_tabelas_grade
Idempotente — tabelas cujo código já existe são ignoradas.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import SessionLocal
from models.tabela_grade import ItemTabelaGrade, TabelaGrade

TABELAS_PADRAO = [
    {
        "codigo": "001",
        "descricao": "COR",
        "itens": [
            {"codigo_curto": "AZU", "descricao": "AZUL", "ordem": 1},
            {"codigo_curto": "VRM", "descricao": "VERMELHO", "ordem": 2},
            {"codigo_curto": "PRT", "descricao": "PRETO", "ordem": 3},
            {"codigo_curto": "BRC", "descricao": "BRANCO", "ordem": 4},
            {"codigo_curto": "CZA", "descricao": "CINZA", "ordem": 5},
            {"codigo_curto": "VRD", "descricao": "VERDE", "ordem": 6},
            {"codigo_curto": "RSA", "descricao": "ROSA", "ordem": 7},
            {"codigo_curto": "BEG", "descricao": "BEGE", "ordem": 8},
        ],
    },
    {
        "codigo": "002",
        "descricao": "TAMANHO",
        "itens": [
            {"codigo_curto": "PP", "descricao": "PP", "ordem": 1},
            {"codigo_curto": "P", "descricao": "P", "ordem": 2},
            {"codigo_curto": "M", "descricao": "M", "ordem": 3},
            {"codigo_curto": "G", "descricao": "G", "ordem": 4},
            {"codigo_curto": "GG", "descricao": "GG", "ordem": 5},
            {"codigo_curto": "G1", "descricao": "G1", "ordem": 6},
            {"codigo_curto": "G2", "descricao": "G2", "ordem": 7},
            {"codigo_curto": "G3", "descricao": "G3", "ordem": 8},
            {"codigo_curto": "TU", "descricao": "TAMANHO ÚNICO", "ordem": 9},
        ],
    },
]


def seed() -> None:
    db = SessionLocal()
    try:
        existentes = {t.codigo for t in db.query(TabelaGrade).all()}
        criadas = 0
        for dados in TABELAS_PADRAO:
            if dados["codigo"] in existentes:
                continue
            tabela = TabelaGrade(codigo=dados["codigo"], descricao=dados["descricao"])
            tabela.itens = [ItemTabelaGrade(**item) for item in dados["itens"]]
            db.add(tabela)
            criadas += 1
        db.commit()
        print(f"{criadas} tabela(s) de grade criada(s); {len(TABELAS_PADRAO) - criadas} já existiam.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
