from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QSystemTrayIcon

from talky.ui import TrayApp


def test_tray_icon_click_does_not_open_dashboard_directly() -> None:
    opened: list[str] = []
    dummy = SimpleNamespace(
        _ready_for_tray_click=True,
        show_settings=lambda: opened.append("opened"),
    )

    TrayApp._on_tray_activated(dummy, QSystemTrayIcon.ActivationReason.Trigger)

    assert opened == []


def test_signal_file_opens_dashboard_and_is_consumed(tmp_path: Path) -> None:
    signal_file = tmp_path / "show_settings.signal"
    signal_file.write_text("12345", encoding="utf-8")
    opened: list[str] = []
    dummy = SimpleNamespace(
        _show_settings_signal_path=lambda: signal_file,
        show_settings=lambda: opened.append("opened"),
        _last_consumed_show_settings_signal_mtime_ns=0,
    )

    TrayApp._consume_show_settings_signal(dummy)

    assert opened == ["opened"]
    assert not signal_file.exists()


def test_controller_signal_suppressed_while_processing() -> None:
    opened: list[str] = []
    dummy = SimpleNamespace(
        _pipeline_state="processing",
        show_settings=lambda: opened.append("opened"),
    )

    TrayApp._show_settings_from_controller(dummy)

    assert opened == []


def test_controller_signal_opens_when_idle() -> None:
    opened: list[str] = []
    dummy = SimpleNamespace(
        _pipeline_state="idle",
        show_settings=lambda: opened.append("opened"),
    )

    TrayApp._show_settings_from_controller(dummy)

    assert opened == ["opened"]
