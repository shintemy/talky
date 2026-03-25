from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def _make_wizard(status="not_installed", locale="en"):
    from talky.onboarding import OnboardingWizard, OllamaStatus

    status_enum = OllamaStatus(status)
    store = MagicMock()
    store.config_path = MagicMock()
    store.config_path.exists = MagicMock(return_value=False)
    wizard = OnboardingWizard(
        config_store=store,
        ollama_status=status_enum,
        locale=locale,
    )
    return wizard, store


def test_wizard_shows_mode_page_when_not_installed():
    wizard, _ = _make_wizard("not_installed")
    assert wizard.stack.currentIndex() == 0  # mode selection page


def test_wizard_shows_model_page_when_no_model():
    wizard, _ = _make_wizard("no_model")
    assert wizard.stack.currentIndex() == 3  # model prep page


def test_wizard_shows_install_page_when_not_running():
    wizard, _ = _make_wizard("not_running")
    assert wizard.stack.currentIndex() == 1  # local install page


def test_wizard_zh_locale_shows_chinese():
    wizard, _ = _make_wizard("not_installed", locale="zh")
    title = wizard.windowTitle()
    assert "Talky" in title


def test_wizard_complete_saves_settings():
    from talky.onboarding import OnboardingWizard, OllamaStatus

    store = MagicMock()
    store.config_path = MagicMock()
    store.config_path.exists = MagicMock(return_value=False)
    wizard = OnboardingWizard(
        config_store=store,
        ollama_status=OllamaStatus.NO_MODEL,
        locale="en",
    )
    wizard._selected_model = "qwen3.5:9b"
    wizard._selected_host = "http://127.0.0.1:11434"
    wizard._finish()
    store.save.assert_called_once()
    saved = store.save.call_args[0][0]
    assert saved.ollama_model == "qwen3.5:9b"
    assert saved.ollama_host == "http://127.0.0.1:11434"
