"""memoria.py — pico de memória do processo durante uma geração.

O spyrrow é Rust: a memória dele não aparece no tracemalloc. Medimos o
working set / RSS do PROCESSO inteiro, amostrado por uma thread enquanto a
geração roda, e devolvemos o maior valor visto. O pico de vida do processo
(PeakWorkingSetSize) não serve, porque não dá para zerar entre gerações.

Sem dependência nova: ctypes (psapi) no Windows, /proc/self/statm no Linux;
em outro sistema devolve None.
"""

from __future__ import annotations

import os
import sys
import threading

_MB = 1024 * 1024


def _rss_windows() -> int | None:
    import ctypes
    from ctypes import wintypes

    class _Contadores(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    c = _Contadores()
    c.cb = ctypes.sizeof(c)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    k32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
    ok = k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return int(c.WorkingSetSize) if ok else None


def _rss_linux() -> int | None:
    try:
        with open("/proc/self/statm", encoding="ascii") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError):
        return None


def rss_bytes() -> int | None:
    """Memória residente atual do processo (bytes), ou None se não sei medir."""
    try:
        if sys.platform == "win32":
            return _rss_windows()
        return _rss_linux()
    except (OSError, AttributeError, ValueError):  # pragma: no cover - plataforma exótica
        return None


class MedidorPico:
    """`with MedidorPico() as m: ...` → m.pico_mb, m.inicio_mb.

    Amostra a cada `intervalo_s` (padrão 50 ms): um pico mais curto que isso
    pode escapar, o que basta para ver se a geração aproxima o teto da máquina.
    """

    def __init__(self, intervalo_s: float = 0.05) -> None:
        self.intervalo_s = intervalo_s
        self.inicio_mb: float | None = None
        self.pico_mb: float | None = None
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None

    def _amostra(self) -> None:
        atual = rss_bytes()
        if atual is not None:
            mb = atual / _MB
            self.pico_mb = mb if self.pico_mb is None else max(self.pico_mb, mb)

    def _laco(self) -> None:
        while not self._parar.wait(self.intervalo_s):
            self._amostra()

    def __enter__(self) -> MedidorPico:
        atual = rss_bytes()
        self.inicio_mb = atual / _MB if atual is not None else None
        self._amostra()
        self._thread = threading.Thread(target=self._laco, name="medidor-memoria", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._parar.set()
        if self._thread is not None:
            self._thread.join()
        self._amostra()
