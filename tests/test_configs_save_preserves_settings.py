from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_save_settings_preserves_runtime_managed_fields(qapp) -> None:
    """Saving from the Configs tab must not wipe fields the UI does not manage.

    The wake-guard counters and gap threshold are mutated at runtime by the
    controller (see AppController._record_wake_guard_rebuild) and persisted.
    A UI settings save rebuilds AppSettings, so it must carry these fields
    through unchanged instead of resetting them to their dataclass defaults.
    """
    from talky.models import AppSettings
    from talky.ui import ConfigsTab

    captured: list[AppSettings] = []
    controller = SimpleNamespace(
        settings=AppSettings(
            ui_locale="en",
            direct_whisper_output=True,
            wake_guard_gap_threshold_s=42.0,
            wake_guard_rebuild_count=7,
            wake_guard_suspected_false_positive_count=3,
        ),
        refresh_hotkey_listener=lambda: None,
        update_settings=lambda s: captured.append(s),
    )

    with (
        patch("talky.ui.check_microphone_granted", return_value=(True, "")),
        patch("talky.ui.check_input_monitoring_granted", return_value=True),
        patch("talky.ui.is_accessibility_trusted", return_value=True),
        patch("talky.models.list_ollama_models", return_value=["qwen3.5:9b"]),
    ):
        tab = ConfigsTab(controller=controller, locale="en")
        # Run the deferred apply synchronously instead of via the event loop.
        with patch("talky.ui.QTimer.singleShot", lambda _ms, fn: fn()):
            tab._save_settings(quiet=True)

    assert captured, "update_settings was never called by _save_settings"
    saved = captured[-1]
    assert saved.wake_guard_rebuild_count == 7
    assert saved.wake_guard_suspected_false_positive_count == 3
    assert saved.wake_guard_gap_threshold_s == 42.0
    assert saved.direct_whisper_output is True
