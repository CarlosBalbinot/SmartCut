"""Exporta as peças do pedido 000001 / OC-0002 exatamente como o motor atual
as recebe (polígono após rotacao_base, rotações pelo sentido do fio,
quantidade = conjuntos × multiplicador do tipo_corte) para
dados/pedido000001_oc0002.json.

Lê o banco de desenvolvimento em modo somente leitura e reaproveita as
funções de produção (_poligono_rotacionado, _rotacoes, _MULT, planejar) —
nada do código de produção é alterado.

Uso (a partir de backend/):  py -3.12 -m experimentos.nesting.exportar_pecas
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from services.nesting_service import _MULT, _poligono_rotacionado, _rotacoes  # noqa: E402
from services.plano_enfesto import planejar  # noqa: E402

OC_ID = "00e7657be5454b13943462bc50cb1658"  # OC-0002 (pedido 000001)
SAIDA = Path(__file__).parent / "dados" / "pedido000001_oc0002.json"


def main() -> None:
    db = sqlite3.connect(f"file:{BACKEND / 'smartcut.db'}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row

    tecidos = {
        r["cor"]: r
        for r in db.execute(
            """select t.cor, l.id lote_id, ct.nome_cor, ct.largura_util_cm, m.max_camadas, m.nome modelo
               from ordem_corte_tecidos t join lotes_tecido l on l.id = t.lote_id
               join cores_tecido ct on ct.id = l.cor_id join modelos_tecido m on m.id = ct.modelo_id
               where t.ordem_corte_id = ?""",
            (OC_ID,),
        )
    }
    itens = list(db.execute("select * from itens_ordem_corte where ordem_corte_id = ?", (OC_ID,)))

    saida = {"oc": "OC-0002", "pedido": "000001", "tecidos": []}
    for cor, tec in tecidos.items():
        qtd = {}
        grupo = None
        for it in itens:
            if it["cor"] == cor:
                qtd[it["tamanho"].strip().upper()] = qtd.get(it["tamanho"].strip().upper(), 0) + it["quantidade"]
                grupo = it["grupo_molde_id"]
        plano = planejar(qtd, tec["max_camadas"], "SEM_SOBRA")
        moldes = list(db.execute("select * from moldes where grupo_id = ?", (grupo,)))
        for n, enf in enumerate(plano["enfestos"], start=1):
            pecas = []
            for tam, conjuntos in enf["conjuntos_por_tamanho"].items():
                for m in moldes:
                    if (m["tamanho"] or "").strip().upper() != tam:
                        continue
                    ns = SimpleNamespace(
                        geometria_json=json.loads(m["geometria_json"]) if m["geometria_json"] else None,
                        area_cm2=m["area_cm2"],
                        rotacao_base=m["rotacao_base"],
                    )
                    pecas.append(
                        {
                            "id": m["id"],
                            "nome": f"{m['peca']} {tam}",
                            "peca": m["peca"],
                            "tamanho": tam,
                            "tipo_corte": m["tipo_corte"],
                            "sentido_fio": m["sentido_fio"],
                            "rotacao_base": m["rotacao_base"],
                            "polygon": _poligono_rotacionado(ns),
                            "quantity": conjuntos * _MULT.get(m["tipo_corte"] or "simples", 1),
                            "rotations": _rotacoes(m["sentido_fio"]),
                        }
                    )
            saida["tecidos"].append(
                {
                    "cor": cor,
                    "tecido": f"{tec['modelo']} — {tec['nome_cor']}",
                    "largura_cm": float(tec["largura_util_cm"]),
                    "enfesto": n,
                    "camadas": enf["camadas"],
                    "conjuntos_por_tamanho": enf["conjuntos_por_tamanho"],
                    "pecas": pecas,
                }
            )

    SAIDA.parent.mkdir(exist_ok=True)
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
    for t in saida["tecidos"]:
        n = sum(p["quantity"] for p in t["pecas"])
        print(f"{t['cor']}: {t['largura_cm']} cm, {t['camadas']} camada(s), {t['conjuntos_por_tamanho']}, {n} peças")


if __name__ == "__main__":
    main()
