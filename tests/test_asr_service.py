from __future__ import annotations

import threading
import time


def test_warm_up_gate_blocks_until_complete() -> None:
    from talky.asr_service import (
        _WARMUP_READY,
        mark_asr_warm_up_complete,
        mark_asr_warm_up_pending,
        reset_asr_runtime_gates_for_tests,
    )

    reset_asr_runtime_gates_for_tests()
    mark_asr_warm_up_pending()

    entered = threading.Event()

    def worker() -> None:
        _WARMUP_READY.wait(timeout=1)
        entered.set()

    thread = threading.Thread(target=worker)
    thread.start()
    time.sleep(0.05)
    assert not entered.is_set()
    mark_asr_warm_up_complete()
    thread.join(timeout=1)
    assert entered.is_set()


def test_build_transcribe_kwargs_forces_transcribe_task() -> None:
    from talky.asr_service import MlxWhisperASR

    kwargs = MlxWhisperASR._build_transcribe_kwargs(
        initial_prompt="你好",
        language="zh",
    )
    assert kwargs["language"] == "zh"
    assert kwargs["task"] == "transcribe"
    assert kwargs["condition_on_previous_text"] is False
    assert kwargs["temperature"] == (0.0,)
