from __future__ import annotations

import time

import pytest

from talky.task_timeout import run_with_timeout


def test_run_with_timeout_returns_value() -> None:
    value = run_with_timeout(lambda: 42, 0.5, label="quick-task")
    assert value == 42


def test_run_with_timeout_raises_inner_exception() -> None:
    def _boom() -> int:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        run_with_timeout(_boom, 0.5, label="failing-task")


def test_run_with_timeout_raises_timeout_error() -> None:
    def _slow() -> int:
        time.sleep(0.3)
        return 1

    with pytest.raises(TimeoutError, match="slow-task timed out"):
        run_with_timeout(_slow, 0.05, label="slow-task")
