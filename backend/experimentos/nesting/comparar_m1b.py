"""comparar_m1b.py — M1-B: v1 × SVGnest corrigido (B2) × v2 (spyrrow + OR-Tools).

Rodada rápida, 1 semente, pedido 000001 / OC-0002, limites 150, 200 e sem
limite. Cada motor × tecido × limite roda num SUBPROCESSO próprio, um de cada
vez (nunca dois motores em paralelo), e o pico de memória é o
PeakWorkingSetSize desse subprocesso somado ao maior pico dos processos que
ele abriu (Node do v1 e do SVGnest) — medido pelo handle do Windows.

Também roda um cenário SINTÉTICO para conferir o espelho dos pares: o mesmo
PRETO, com as COSTAS cadastradas como `par` em vez de `par_sem_espelho` (a
OC real não tem nenhum `par`). O SVG marca a metade espelhada e o script
confere a geometria de cada metade contra o molde.

Saída em resultados/m1b/: tabela.md, resultados.json, um SVG por motor × caso
e um SVG por mesa do v2.

Uso (a partir de backend/):
  py -3.12 -m experimentos.nesting.comparar_m1b
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from shapely.affinity import translate  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402

from experimentos.nesting import comum  # noqa: E402

SAIDA = comum.RESULTADOS / "m1b"
LIMITES: tuple[float | None, ...] = (150.0, 200.0, None)
MOTORES = ("v1", "b2", "v2")
NOME_MOTOR = {
    "v1": "v1 atual",
    "b2": "SVGnest corrigido (B2)",
    "v2": "v2 sparrow + OR-Tools",
}
# B2 do M0: NFP saneado + contorno a 0,1 cm e inflado 0,1 cm, 10 gerações
SVG_OK = {"curveTolerance": 0.1, "inflate": 0.1, "sanearNfp": True}
SEMENTE_B2 = 1
SEMENTE_V2 = 0
# SVGnest "sem limite": uma mesa bem longa (como o B4 do M0)
MESA_LONGA_CM = 5000.0
CASO_PAR = "PRETO (COSTAS como par, sintético)"


# ── Memória dos processos filhos (Windows) ───────────────────────────────────


def _pico_handle_mb(handle: int) -> float | None:
    """PeakWorkingSetSize de um processo pelo handle (Popen._handle)."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class _C(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (n, ctypes.c_size_t)
            for n in (
                "PeakWorkingSetSize",
                "WorkingSetSize",
                "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage",
                "PagefileUsage",
                "PeakPagefileUsage",
            )
        ]

    c = _C()
    c.cb = ctypes.sizeof(c)
    k32 = ctypes.WinDLL("kernel32")
    k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    k32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
    if not k32.K32GetProcessMemoryInfo(int(handle), ctypes.byref(c), c.cb):
        return None
    return c.PeakWorkingSetSize / 2**20


class _PopenMedido(subprocess.Popen):
    """Popen que guarda o pico de memória do filho quando ele termina."""

    picos: list[float] = []

    def wait(self, timeout=None):  # noqa: D102
        rc = super().wait(timeout)
        handle = getattr(self, "_handle", None)
        if handle is not None:
            pico = _pico_handle_mb(handle)
            if pico is not None:
                _PopenMedido.picos.append(pico)
        return rc


# ── Um caso (roda no subprocesso) ────────────────────────────────────────────


def _tecido(cor: str) -> dict:
    dados = comum.carregar()
    if cor == CASO_PAR:
        tec = copy.deepcopy(next(t for t in dados["tecidos"] if t["cor"] == "PRETO"))
        for p in tec["pecas"]:
            if p["tipo_corte"] == "par_sem_espelho":
                p["tipo_corte"] = "par"
        tec["cor"] = CASO_PAR
        return tec
    return next(t for t in dados["tecidos"] if t["cor"] == cor)


def _pecas_v2(tec: dict) -> list:
    from services.nesting_v2.geometria import Peca

    return [
        Peca(
            id=p["id"],
            poligono=p["polygon"],
            quantidade=p["quantity"],
            rotacoes=tuple(float(r) for r in p["rotations"]),
            tipo_corte=p["tipo_corte"],
            peca=p.get("peca"),
            tamanho=p.get("tamanho"),
            grupo_nome=p.get("grupo_nome"),
        )
        for p in tec["pecas"]
        if p["quantity"] > 0
    ]


def _rodar_caso(motor: str, cor: str, limite: float | None) -> dict:
    from experimentos.nesting import cand_a_atual, motores

    tec = _tecido(cor)
    extra: dict = {}
    t0 = time.perf_counter()
    if motor == "v1":
        partes, _, _ = cand_a_atual.rodar(tec, limite)
    elif motor == "b2":
        brutas, info = motores.svgnest(
            tec["pecas"], tec["largura_cm"], limite or MESA_LONGA_CM, generations=10, seed=SEMENTE_B2, **SVG_OK
        )
        partes = [comum.normalizar_parte(p) for p in brutas]
        extra["nao_encaixadas"] = info.get("unplaced")
    else:
        from services.nesting_v2 import gerar

        r = gerar(_pecas_v2(tec), tec["largura_cm"], limite, tec["camadas"], seed=SEMENTE_V2)
        partes = [
            [
                {
                    "id": pl["id"],
                    "rotation": pl["rotation"],
                    "espelhada": pl["espelhada"],
                    "points": cand_a_atual._pontos(pl["polygon"], pl["rotation"], pl["x"], pl["y"]),
                }
                for pl in m.pecas
            ]
            for m in r.mesas
        ]
        extra = {
            "moldes_por_mesa": [m.moldes(r.camadas) for m in r.mesas],
            "resumo_enfesto": r.resumo_enfesto(),
            "pico_interno_mb": r.pico_memoria_mb,
            "chamadas_spyrrow": r.chamadas_spyrrow,
        }
    return {"partes": partes, "segundos": time.perf_counter() - t0, **extra}


def _filho(motor: str, cor: str, limite: str, saida: str) -> None:
    subprocess.Popen = _PopenMedido  # mede o Node do v1 e do SVGnest
    res = _rodar_caso(motor, cor, None if limite == "-" else float(limite))
    res["pico_netos_mb"] = max(_PopenMedido.picos, default=0.0)
    Path(saida).write_text(json.dumps(res), encoding="utf-8")


def _executar(motor: str, cor: str, limite: float | None) -> dict:
    """Roda um caso num subprocesso e espera terminar (um por vez)."""
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "caso.json"
        cmd = [sys.executable, "-m", "experimentos.nesting.comparar_m1b", "--caso", motor, cor]
        cmd += ["-" if limite is None else f"{limite:g}", str(saida)]
        proc = subprocess.Popen(cmd, cwd=BACKEND)
        rc = proc.wait()
        pico = _pico_handle_mb(proc._handle) or 0.0
        if rc:
            raise RuntimeError(f"{motor} {cor} {limite}: saiu com {rc}")
        res = json.loads(saida.read_text(encoding="utf-8"))
    res["pico_mb"] = pico + res.pop("pico_netos_mb", 0.0)
    return res


# ── Conferência do espelho ───────────────────────────────────────────────────


def _conferir_espelho(tec: dict, partes: list[list[dict]]) -> dict:
    """Cada peça de `par` confere com o molde (normal) ou com o molde
    espelhado sobre o fio (espelhada) — e não com o outro; as duas metades
    de cada par caem na mesma mesa, uma de cada tipo."""
    from services.nesting_v2.geometria import eixo_do_fio, espelhar, normalizar, rotacionar

    def ancorado(pts):
        pg = Polygon(pts).buffer(0)
        minx, miny, _, _ = pg.bounds
        return translate(pg, -minx, -miny)

    def igual(a, b):
        return a.symmetric_difference(b).area < 0.5

    por_id = {p["id"]: p for p in tec["pecas"]}
    ok = erros = 0
    problemas: list[str] = []
    for i, parte in enumerate(partes, start=1):
        cont: dict[str, list[int]] = {}
        for pc in parte:
            molde = por_id[pc["id"]]
            if molde["tipo_corte"] != "par":
                continue
            base = normalizar(molde["polygon"])
            normal = ancorado(rotacionar(base, pc["rotation"]))
            espelho = ancorado(rotacionar(espelhar(base, eixo_do_fio(tuple(molde["rotations"]))), pc["rotation"]))
            real = ancorado(pc["points"])
            bate_normal, bate_esp = igual(real, normal), igual(real, espelho)
            if igual(normal, espelho):
                problemas.append(f"mesa {i}: {molde['nome']} é simétrico — espelho não se distingue")
            certo = bate_esp and not bate_normal if pc.get("espelhada") else bate_normal and not bate_esp
            ok += certo
            erros += not certo
            if not certo:
                problemas.append(f"mesa {i}: {molde['nome']} espelhada={pc.get('espelhada')} não confere")
            c = cont.setdefault(pc["id"], [0, 0])
            c[int(bool(pc.get("espelhada")))] += 1
        for pid, (normais, espelhadas) in cont.items():
            if normais != espelhadas:
                problemas.append(f"mesa {i}: {por_id[pid]['nome']} {normais} normais × {espelhadas} espelhadas")
                erros += 1
    return {"pecas_conferidas": ok + erros, "ok": ok, "erros": erros, "problemas": problemas}


# ── Relatório ────────────────────────────────────────────────────────────────


def _slug(cor: str, limite: float | None) -> str:
    base = {"PRETO": "preto", "VERDE MILITAR": "verde_militar", CASO_PAR: "preto_par_espelhado"}[cor]
    return f"{base}_{int(limite) if limite else 'sem_limite'}"


def _lim_txt(limite: float | None) -> str:
    return f"{limite:g} cm" if limite else "sem limite"


def _moldes_txt(linhas: list[dict]) -> str:
    itens = []
    for m in linhas:
        nome = f"{m['peca'] or m['molde_id'][:6]} {m['tamanho'] or ''}".strip()
        esp = f" ({m['espelhadas']} esp.)" if m.get("espelhadas") else ""
        itens.append(f"{nome} x{m['por_camada']}{esp}")
    return ", ".join(itens)


def _svg_mesa(tec: dict, parte: list[dict], i: int, total: int, titulo: str, destino: Path, limite) -> None:
    comp = comum.comprimento(parte)
    ef = sum(comum.area(pc["points"]) for pc in parte) / (tec["largura_cm"] * comp) if comp else 0
    m = {
        "metros": comp / 100,
        "partes": 1,
        "aproveitamento_medio": ef,
        "aproveitamento_pior": ef,
        "aproveitamento_partes": [ef],
        "segundos": 0.0,
        "valido": True,
    }
    comum.svg(tec, [parte], m, f"{titulo} — mesa {i}/{total}", destino, limite)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass
    SAIDA.mkdir(parents=True, exist_ok=True)
    casos = [(cor, lim, mot) for cor in ("PRETO", "VERDE MILITAR") for lim in LIMITES for mot in MOTORES]
    casos.append((CASO_PAR, 150.0, "v2"))

    linhas: list[str] = []
    mesas_md: list[str] = []
    todos: list[dict] = []
    espelho: dict | None = None
    for cor, limite, motor in casos:
        print(f"→ {NOME_MOTOR[motor]} · {cor} · {_lim_txt(limite)}", flush=True)
        tec = _tecido(cor)
        res = _executar(motor, cor, limite)
        partes = res["partes"]
        m = comum.metricas(tec, partes, res["segundos"], limite)
        slug = _slug(cor, limite)
        titulo = f"{NOME_MOTOR[motor]} — {cor} · {tec['largura_cm']:g} cm · {_lim_txt(limite)}"
        comum.svg(tec, partes, m, titulo, SAIDA / f"{motor}_{slug}.svg", limite)
        val = "sim" if m["valido"] else "NÃO: " + "; ".join(m["problemas"][:2])
        linhas.append(
            f"| {cor} | {_lim_txt(limite)} | {NOME_MOTOR[motor]} | {m['metros']:.2f} | {m['partes']} | "
            f"{m['aproveitamento_medio'] * 100:.1f}% | {m['aproveitamento_pior'] * 100:.1f}% | "
            f"{m['segundos']:.0f} s | {res['pico_mb']:.0f} MB | {val} |"
        )
        print("   " + linhas[-1], flush=True)
        registro = {"tecido": cor, "limite": limite, "motor": motor, "pico_mb": round(res["pico_mb"], 1), **m}
        if motor == "v2":
            registro.update(
                {k: res[k] for k in ("moldes_por_mesa", "resumo_enfesto", "pico_interno_mb", "chamadas_spyrrow")}
            )
            for i, parte in enumerate(partes, start=1):
                _svg_mesa(tec, parte, i, len(partes), titulo, SAIDA / f"v2_{slug}_mesa{i}.svg", limite)
            grade = " · ".join(f"{g['tamanho']} {g['pecas']}" for g in res["resumo_enfesto"]["pecas_por_tamanho"])
            mesas_md.append(
                f"\n### {cor} · {_lim_txt(limite)} — {m['partes']} mesa(s), {m['metros']:.2f} m\n\n"
                f"Resumo do enfesto (grade por tamanho, peças por camada): {grade} · "
                f"{tec['camadas']} camada(s)\n\n"
                "| Mesa | Comprimento | Aprov. | Moldes que a mesa corta (por camada) | SVG |\n|---:|---:|---:|---|---|\n"
                + "\n".join(
                    f"| {i} | {c:.1f} cm | {e * 100:.1f}% | {_moldes_txt(ml)} | `v2_{slug}_mesa{i}.svg` |"
                    for i, (c, e, ml) in enumerate(
                        zip(m["comprimentos_cm"], m["aproveitamento_partes"], res["moldes_por_mesa"]), start=1
                    )
                )
            )
        if cor == CASO_PAR:
            espelho = _conferir_espelho(tec, partes)
            registro["conferencia_espelho"] = espelho
        todos.append(registro)

    cab = (
        "| Tecido | Limite | Motor | Metros | Mesas | Aprov. médio | Pior mesa | Tempo | Memória (pico) | Válido |\n"
        "|---|---|---|---:|---:|---:|---:|---:|---:|:-:|"
    )
    md = (
        "# M1-B — v1 × SVGnest corrigido (B2) × v2 (pedido 000001 / OC-0002)\n\n"
        "Rodada rápida, 1 semente (B2 seed 1, 10 gerações; v2 seed 0, spyrrow com 2 workers). "
        "Um motor por vez, cada um num subprocesso; memória = pico do working set do subprocesso "
        "+ pico do Node que ele abriu. Validação: sobreposição (shapely), largura, contagem e limite.\n\n"
        + cab
        + "\n"
        + "\n".join(linhas)
        + "\n\n## Mesas do v2 (tabela por mesa = moldes)\n"
        + "\n".join(mesas_md)
        + "\n"
    )
    if espelho:
        md += (
            f"\n## Conferência do espelho ({CASO_PAR})\n\n"
            f"{espelho['ok']} de {espelho['pecas_conferidas']} peças de `par` conferem com o molde "
            f"(normal) ou com o espelho sobre o fio (espelhada); erros: {espelho['erros']}.\n"
            + "".join(f"- {p}\n" for p in espelho["problemas"])
        )
    (SAIDA / "tabela.md").write_text(md, encoding="utf-8")
    (SAIDA / "resultados.json").write_text(json.dumps(todos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--caso", nargs=4, metavar=("MOTOR", "TECIDO", "LIMITE", "SAIDA"))
    args = ap.parse_args()
    if args.caso:
        _filho(*args.caso)
    else:
        main()
