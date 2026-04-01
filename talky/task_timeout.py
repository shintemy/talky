from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def run_with_timeout(func: Callable[[], T], timeout_s: float, *, label: str) -> T:
    result_q: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

    def _runner() -> None:
        try:
            result_q.put((True, func()))
        except Exception as exc:  # noqa: BLE001
            result_q.put((False, exc))

    worker = threading.Thread(target=_runner, daemon=True)
    worker.start()
    worker.join(timeout_s)
    if worker.is_alive():
        raise TimeoutError(f"{label} timed out after {timeout_s:.0f}s")
    ok, value = result_q.get_nowait()
    if ok:
        return value  # type: ignore[return-value]
    raise value  # type: ignore[misc]
