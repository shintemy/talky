from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

from talky.controller import AppController
from talky.models import AppSettings
from talky.ui import SettingsWindow

_app = QApplication.instance() or QApplication([])


class _FakeConfigStore:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def load(self) -> AppSettings:
        return self._settings

    def save(self, settings: AppSettings) -> None:
        self._settings = settings


def _build_window() -> tuple[AppController, SettingsWindow]:
    controller = AppController(_FakeConfigStore(AppSettings(ollama_model="qwen3.5:4b")))
    return controller, SettingsWindow(controller)


def test_prompt_is_persisted_when_switching_away_from_prompt_tab() -> None:
    controller, window = _build_window()
    edited_prompt = "Custom prompt from tab switch"

    window._on_tab_changed(3)
    window._prompt_tab._editor.setPlainText(edited_prompt)  # noqa: SLF001
    window._on_tab_changed(0)

    assert controller.settings.custom_llm_prompt == edited_prompt
    window._on_tab_changed(3)
    assert window._prompt_tab._editor.toPlainText() == edited_prompt  # noqa: SLF001
