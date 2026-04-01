from __future__ import annotations

from talky.processing_guard import should_timeout_processing


def test_processing_guard_threshold_behavior() -> None:
    assert not should_timeout_processing(0.5, 45.0)
    assert should_timeout_processing(45.0, 45.0)
