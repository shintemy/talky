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


def test_daily_prompt_saved_via_save_button_persists_and_survives_tab_switch() -> None:
    controller, window = _build_window()
    edited_prompt = "Custom prompt from tab switch"

    # Enter the Prompt tab and edit + save the Daily prompt module.
    window._on_tab_changed(3)
    prompt_tab = window._prompt_tab
    prompt_tab._daily_enter_edit()  # noqa: SLF001
    prompt_tab._daily_widgets["editor"].setPlainText(edited_prompt)  # noqa: SLF001
    prompt_tab._daily_save()  # noqa: SLF001

    # Saving the Daily prompt persists it to settings.
    assert controller.settings.custom_llm_prompt == edited_prompt

    # Switching away (which cancels any in-progress edit) and back re-loads the
    # saved value into the editor.
    window._on_tab_changed(0)
    window._on_tab_changed(3)
    assert (
        window._prompt_tab._daily_widgets["editor"].toPlainText() == edited_prompt  # noqa: SLF001
    )
