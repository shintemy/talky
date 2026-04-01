from __future__ import annotations

DEFAULT_WAKE_GUARD_THRESHOLD_S = 20.0
MIN_WAKE_GUARD_THRESHOLD_S = 5.0
MAX_WAKE_GUARD_THRESHOLD_S = 120.0
DEFAULT_FALSE_POSITIVE_DENSE_WINDOW_S = 90.0


def should_rebuild_hotkey(elapsed_seconds: float, threshold_seconds: float) -> bool:
    return elapsed_seconds >= threshold_seconds


def normalize_wake_guard_threshold(value: float | int | str | None) -> float:
    try:
        threshold = float(value)
    except Exception:
        return DEFAULT_WAKE_GUARD_THRESHOLD_S
    return max(MIN_WAKE_GUARD_THRESHOLD_S, min(MAX_WAKE_GUARD_THRESHOLD_S, threshold))


def should_mark_suspected_false_positive(
    *,
    last_rebuild_ts: float,
    now_ts: float,
    dense_window_s: float = DEFAULT_FALSE_POSITIVE_DENSE_WINDOW_S,
) -> bool:
    if last_rebuild_ts <= 0:
        return False
    return (now_ts - last_rebuild_ts) < dense_window_s
