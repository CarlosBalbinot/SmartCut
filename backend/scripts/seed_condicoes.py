"""Popula as condições de pagamento padrão da Vaidosa.

Uso: py -3.12 -m scripts.seed_condicoes
Idempotente — condições cujo código já existe são ignoradas.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import SessionLocal
from models.condicao_pagamento import CondicaoPagamento

CONDICOES_PADRAO = [
    {"codigo": "000", "descricao": "A VISTA", "tipo": "intervalo", "condicao": "0"},
    {"codigo": "001", "descricao": "30 DIAS", "tipo": "intervalo", "condicao": "30"},
    {"codigo": "002", "descricao": "30/60 DIAS", "tipo": "intervalo", "condicao": "30/60"},
    {"codigo": "003", "descricao": "30/60/90 DIAS", "tipo": "intervalo", "condicao": "30/60/90"},
    {"codigo": "004", "descricao": "15/30 DIAS", "tipo": "intervalo", "condicao": "15/30"},
    {"codigo": "005", "descricao": "45 DIAS", "tipo": "intervalo", "condicao": "45"},
]


def seed() -> None:
    db = SessionLocal()
    try:
        existentes = {c.codigo for c in db.query(CondicaoPagamento).all()}
        criadas = 0
        for dados in CONDICOES_PADRAO:
            if dados["codigo"] in existentes:
                continue
            db.add(CondicaoPagamento(**dados))
            criadas += 1
        db.commit()
        print(f"{criadas} condição(ões) de pagamento criada(s); {len(CONDICOES_PADRAO) - criadas} já existiam.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
