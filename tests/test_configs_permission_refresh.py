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
