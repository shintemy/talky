from __future__ import annotations

DEFAULT_PERIODIC_MAINTENANCE_INTERVAL_S = 6 * 3600


def should_run_periodic_maintenance(
    *,
    elapsed_since_last_s: float,
    interval_s: float = DEFAULT_PERIODIC_MAINTENANCE_INTERVAL_S,
    is_recording: bool,
    is_processing: bool,
) -> bool:
    if is_recording or is_processing:
        return False
    return elapsed_since_last_s >= interval_s
