"""medir_oc — roda a geração de uma Ordem de Corte no banco de CÓPIA e mede o
resultado (tempo, mesas, tecido, perfil de cada risco). Ferramenta de
diagnóstico: o banco real nunca é tocado.

A cópia em %TEMP% é refeita a cada rodada, porque `gerar_de_entradas` grava os
encaixes (é o mesmo caminho da tela) — sem isso a segunda medição compararia a
simulação de ontem com a de hoje. Cada rodada parte do estado gravado.

Uso (a partir de backend/):
    py -3.12 -m scripts.medir_oc 49196028...            # o que está gravado
    py -3.12 -m scripts.medir_oc 49196028... --simular # recalcula e mede
    py -3.12 -m scripts.medir_oc 49196028... --tempo 600
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

# O console do Windows é cp1252 e as regras do perfil têm "≤" e "·".
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# O banco de CÓPIA vem antes de qualquer import do app (database.py lê a
# variável na importação).
#
# A cópia é refeita a CADA rodada, e não só quando não existe: `gerar_de_entradas`
# grava os encaixes (é o mesmo caminho da tela), então manter a cópia faria a
# segunda medição comparar a simulação anterior com a simulação de hoje. Para
# repetir a mesma OC, é preciso partir do estado gravado de novo.
if "--copia" in sys.argv or os.environ.get("SMARTCUT_DB_PATH") is None:
    origem = Path(__file__).resolve().parents[1] / "smartcut.db"
    destino = Path(tempfile.gettempdir()) / "smartcut_medir.db"
    destino.write_bytes(origem.read_bytes())
    os.environ["SMARTCUT_DB_PATH"] = str(destino)

from database import SessionLocal  # noqa: E402
from models.ordem_corte import OrdemCorte  # noqa: E402
from models.pedido import PedidoVenda  # noqa: E402
from services import ordem_corte_service as ocs  # noqa: E402
from services import nesting_service  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("oc", help="id da Ordem de Corte (ou do pedido, se --por-pedido)")
    ap.add_argument(
        "--simular",
        action="store_true",
        help="recalcula em vez de mostrar o gravado (a gravação vai para a cópia descartável, nunca para o banco real)",
    )
    ap.add_argument("--tempo", type=int, default=None, help="tempo_maximo_s do orçamento")
    ap.add_argument("--qualidade", default="AUTOMATICO")
    args = ap.parse_args()

    db = SessionLocal()
    oc = db.get(OrdemCorte, uuid.UUID(args.oc))
    if oc is None:
        print(f"OC {args.oc} não encontrada.")
        return 1
    pedido = db.get(PedidoVenda, oc.pedido_id)
    print(f"OC {oc.id} · pedido {pedido.numero} · {oc.status} · qualidade {oc.qualidade}")
    print(f"{len(oc.itens)} itens · {sum(i.quantidade for i in oc.itens)} peças\n")

    if not args.simular:
        print("— o que está gravado —")
        encaixes = sorted(oc.encaixes, key=lambda e: e.numero)
        for e in encaixes:
            mapa = e.mapa_json or {}
            qual = mapa.get("qualidade_automatica") or {}
            nome = mapa.get("tecido_nome") or "—"
            print(
                f"  #{e.numero:>3} {nome[:26]:<26} {qual.get('pecas', '?'):>3} peças  "
                f"{e.comp_metros:>6.2f} m  cam={e.num_camadas:>2}  "
                f"{mapa.get('qualidade_perfil') or '-':<11} {qual.get('regra', '')}"
            )
        total = sum(e.comp_metros for e in encaixes)
        print(f"  TOTAL {len(encaixes)} mesas · {total:.2f} m\n")

    cfg = nesting_service.config_producao(db)
    if args.tempo:
        cfg["tempo_maximo_oc_s"] = args.tempo
    print(
        f"— simulando (tempo_maximo_oc_s={cfg['tempo_maximo_oc_s']}, qualidade {args.qualidade}, "
        f"mesa {oc.comprimento_max_cm or cfg['comprimento_max_mesa_cm']} cm) —"
    )
    t0 = time.monotonic()
    entradas, avisos_oc = ocs.montar_pares_oc(db, oc)
    for a in avisos_oc:
        print(f"  aviso do pedido: {a}")
    # A entrada da decisão é o "Avançado" da OC (AUTOMATICO quando não há
    # escolha manual) — NÃO o oc.tipo_enfesto, que é o RESULTADO que a decisão
    # gravou. Passar o resultado trava o tipo e a comparação nem roda.
    avancado = ocs.enfesto_avancado(oc)
    resultado = nesting_service.gerar_de_entradas(
        db,
        pedido,
        entradas,
        modo=avancado["modo_camadas"],
        tipo_enfesto=avancado["tipo_enfesto"],
        ordem_corte_id=oc.id,
        descricao=f"{oc.numero} · Pedido {pedido.numero}",
        # O comprimento que a OC gravada usou — não o da configuração, que
        # pode ter mudado desde então (comparar antes/depois exige o mesmo).
        comprimento_max_cm=oc.comprimento_max_cm or cfg["comprimento_max_mesa_cm"],
        qualidade=args.qualidade,
        tempo_maximo_s=float(cfg["tempo_maximo_oc_s"]),
    )
    dt = time.monotonic() - t0

    for aviso in resultado["avisos"]:
        print(f"  aviso: {aviso}")
    print("\n— decisão de enfesto —")
    for d in resultado.get("decisoes", []):
        print(f"  {str(d.get('tecido'))[:30]:<30} {d.get('tipo_nome')} · {d.get('regra')}")
        for c in d.get("candidatos", []):
            marca = "escolhido" if c.get("escolhido") else ("avaliado" if c.get("avaliado") else "não avaliado")
            print(
                f"      {c.get('rotulo', ''):<40} {marca:<13} {c.get('mesas', 0):>3} mesas  {c.get('metros', 0):>7.2f} m  {c.get('segundos', 0):.1f} s"
            )

    print("\n— resultado —")
    perfis: dict[str, int] = {}
    for r in resultado["encaixes"]:
        perfil = r.get("qualidade_perfil") or "?"
        perfis[perfil] = perfis.get(perfil, 0) + 1
        qual = r.get("qualidade_automatica") or {}
        print(
            f"  {str(r.get('tecido_nome'))[:26]:<26} {qual.get('pecas', '?'):>3} peças  "
            f"{r.get('comp_metros', 0):>6.2f} m  cam={r.get('num_camadas', 0):>2}  "
            f"{perfil:<11} {qual.get('regra', '')}"
        )
    total = sum(float(r.get("comp_metros", 0)) for r in resultado["encaixes"])
    print(f"\n  {len(resultado['encaixes'])} mesas · {total:.2f} m de tecido · {dt:.1f} s")
    print("  perfis: " + ", ".join(f"{p} {n} mesas" for p, n in sorted(perfis.items())))

    if oc.encaixes:
        # comp_metros vem Decimal do banco — somar com float do resumo estoura.
        antes_m = float(sum(e.comp_metros for e in oc.encaixes))
        print(
            f"\n  gravado antes: {len(oc.encaixes)} mesas · {antes_m:.2f} m"
            f"  →  agora: {len(resultado['encaixes'])} mesas · {total:.2f} m"
            f"  ({(total - antes_m) / antes_m * 100:+.2f}% de tecido)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
