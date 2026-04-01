from __future__ import annotations

from talky.processing_guard import (
    estimate_asr_timeout_seconds,
    estimate_processing_timeout_seconds,
    should_timeout_processing,
)


def test_should_timeout_processing() -> None:
    assert not should_timeout_processing(10.0, 45.0)
    assert should_timeout_processing(45.0, 45.0)
    assert should_timeout_processing(60.0, 45.0)


def test_estimate_asr_timeout_seconds() -> None:
    assert estimate_asr_timeout_seconds(0.0) == 35.0
    assert estimate_asr_timeout_seconds(40.0) == 95.0
    assert estimate_asr_timeout_seconds(200.0) == 180.0


def test_estimate_processing_timeout_seconds() -> None:
    assert estimate_processing_timeout_seconds(0.0) == 70.0
    assert estimate_processing_timeout_seconds(40.0) == 130.0
    assert estimate_processing_timeout_seconds(200.0) == 215.0
