"""Disputa entre sessões para os testes de concorrência (F0, passo 0).

`disputar(fabrica, n, fn)` roda `fn(sessao, indice)` em `n` threads, cada uma
com a sua sessão (e, portanto, a sua conexão), liberadas juntas por um
`threading.Barrier`. Nenhuma exceção se perde: cada thread devolve um
`Resultado` com o valor ou o erro, e o teste decide o que é esperado (ex.:
exatamente um 200 e um 409).

A sessão é criada antes da barreira, mas a conexão só é pega no primeiro
comando de `fn` — depois da barreira —, então a disputa pelo banco é real.
O pool do engine do app (QueuePool: 5 + 10 de overflow) limita a 15 as
conexões simultâneas; acima disso as threads esperam por conexão.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session


@dataclass
class Resultado:
    indice: int
    valor: Any = None
    erro: BaseException | None = None

    @property
    def ok(self) -> bool:
        return self.erro is None


def disputar(
    fabrica: Callable[[], Session],
    n: int,
    fn: Callable[[Session, int], Any],
    *,
    timeout: float = 30.0,
) -> list[Resultado]:
    """Roda `fn(sessao, indice)` em `n` threads ao mesmo tempo e devolve um
    `Resultado` por thread, na ordem dos índices. Thread que não termina em
    `timeout` segundos falha o teste (AssertionError)."""
    barreira = threading.Barrier(n, timeout=timeout)
    resultados = [Resultado(i) for i in range(n)]

    def alvo(i: int) -> None:
        sessao = fabrica()
        try:
            barreira.wait()
            resultados[i].valor = fn(sessao, i)
        except BaseException as exc:  # o teste decide o que é esperado
            resultados[i].erro = exc
            try:
                sessao.rollback()
            except Exception:
                pass
        finally:
            sessao.close()

    threads = [threading.Thread(target=alvo, args=(i,), name=f"disputa-{i}", daemon=True) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout)
    presas = [t.name for t in threads if t.is_alive()]
    assert not presas, f"Threads não terminaram em {timeout:g} s: {', '.join(presas)}"
    return resultados


def erros(resultados: list[Resultado]) -> list[BaseException]:
    return [r.erro for r in resultados if r.erro is not None]
