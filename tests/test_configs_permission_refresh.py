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


def test_configs_tab_refreshes_hotkey_when_input_monitoring_granted(qapp) -> None:
    from talky.ui import ConfigsTab

    refresh_calls: list[str] = []
    controller = SimpleNamespace(
        settings=SimpleNamespace(ui_locale="en"),
        refresh_hotkey_listener=lambda: refresh_calls.append("refresh"),
    )

    with (
        patch("talky.ui.check_microphone_granted", return_value=(True, "")),
        patch("talky.ui.check_input_monitoring_granted", side_effect=[False, True]),
        patch("talky.ui.is_accessibility_trusted", return_value=True),
    ):
        tab = ConfigsTab(controller=controller, locale="en")
        tab._refresh_permission_status()
        assert refresh_calls == []

        tab._refresh_permission_status()
        assert refresh_calls == ["refresh"]


def test_validate_mode_ready_accepts_any_installed_model(qapp) -> None:
    from talky.models import AppSettings
    from talky.ui import ConfigsTab

    controller = SimpleNamespace(
        settings=AppSettings(ui_locale="en"),
        refresh_hotkey_listener=lambda: None,
    )
    with (
        patch("talky.ui.check_microphone_granted", return_value=(True, "")),
        patch("talky.ui.check_input_monitoring_granted", return_value=True),
        patch("talky.ui.is_accessibility_trusted", return_value=True),
        patch("talky.models.list_ollama_models", return_value=["gemma4:e2b"]),
    ):
        tab = ConfigsTab(controller=controller, locale="en")
        ok, reason = tab._validate_mode_ready(
            usage_mode="vibecoding",
            mode="local",
            ollama_host="http://127.0.0.1:11434",
            ollama_model="qwen3.5:9b",  # NOT installed, but gemma4 is
        )
    assert ok is True
    assert reason == ""


def test_validate_mode_ready_fails_when_no_models(qapp) -> None:
    from talky.models import AppSettings
    from talky.ui import ConfigsTab

    controller = SimpleNamespace(
        settings=AppSettings(ui_locale="en"),
        refresh_hotkey_listener=lambda: None,
    )
    with (
        patch("talky.ui.check_microphone_granted", return_value=(True, "")),
        patch("talky.ui.check_input_monitoring_granted", return_value=True),
        patch("talky.ui.is_accessibility_trusted", return_value=True),
        patch("talky.models.list_ollama_models", return_value=[]),
    ):
        tab = ConfigsTab(controller=controller, locale="en")
        ok, _reason = tab._validate_mode_ready(
            usage_mode="vibecoding",
            mode="local",
            ollama_host="http://127.0.0.1:11434",
            ollama_model="qwen3.5:9b",
        )
    assert ok is False
