from __future__ import annotations

from talky.periodic_maintenance import (
    DEFAULT_PERIODIC_MAINTENANCE_INTERVAL_S,
    should_run_periodic_maintenance,
)


def test_periodic_maintenance_default_interval_is_six_hours() -> None:
    assert DEFAULT_PERIODIC_MAINTENANCE_INTERVAL_S == 6 * 3600


def test_periodic_maintenance_waits_until_interval_elapsed() -> None:
    assert not should_run_periodic_maintenance(
        elapsed_since_last_s=5 * 3600,
        is_recording=False,
        is_processing=False,
    )
    assert should_run_periodic_maintenance(
        elapsed_since_last_s=6 * 3600,
        is_recording=False,
        is_processing=False,
    )


def test_periodic_maintenance_defers_while_recording_or_processing() -> None:
    assert not should_run_periodic_maintenance(
        elapsed_since_last_s=7 * 3600,
        is_recording=True,
        is_processing=False,
    )
    assert not should_run_periodic_maintenance(
        elapsed_since_last_s=7 * 3600,
        is_recording=False,
        is_processing=True,
    )
