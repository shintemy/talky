from __future__ import annotations

from talky.wake_guard import (
    normalize_wake_guard_threshold,
    should_mark_suspected_false_positive,
    should_rebuild_hotkey,
)


def test_wake_guard_does_not_rebuild_for_short_stall() -> None:
    # Simulate short UI/main-thread stalls.
    assert not should_rebuild_hotkey(2.0, 20.0)
    assert not should_rebuild_hotkey(19.99, 20.0)


def test_wake_guard_rebuilds_for_sleep_wake_gap() -> None:
    # Simulate a sleep/wake gap where timer ticks are delayed.
    assert should_rebuild_hotkey(20.0, 20.0)
    assert should_rebuild_hotkey(47.5, 20.0)


def test_wake_guard_handles_repeated_sleep_wake_cycles() -> None:
    threshold = 20.0
    elapsed_seq = [25.0, 3.0, 31.0, 1.0, 22.0]
    rebuilds = [should_rebuild_hotkey(value, threshold) for value in elapsed_seq]
    assert rebuilds == [True, False, True, False, True]


def test_normalize_wake_guard_threshold_bounds() -> None:
    assert normalize_wake_guard_threshold(30.0) == 30.0
    assert normalize_wake_guard_threshold(1.0) == 5.0
    assert normalize_wake_guard_threshold(999.0) == 120.0
    assert normalize_wake_guard_threshold("bad") == 20.0


def test_suspected_false_positive_when_rebuilds_too_dense() -> None:
    assert should_mark_suspected_false_positive(last_rebuild_ts=100.0, now_ts=130.0, dense_window_s=90.0)
    assert not should_mark_suspected_false_positive(last_rebuild_ts=100.0, now_ts=250.0, dense_window_s=90.0)
