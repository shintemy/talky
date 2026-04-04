from __future__ import annotations

import threading
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import SimpleNamespace

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QApplication

from talky.controller import AppController
from talky.models import AppSettings

_app = QApplication.instance() or QApplication([])


class _FakeConfigStore:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def load(self) -> AppSettings:
        return self._settings

    def save(self, settings: AppSettings) -> None:
        self._settings = settings


def _wait_until(predicate, timeout_s: float = 1.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        _app.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    _app.processEvents()
    assert predicate()


def _build_controller() -> AppController:
    settings = AppSettings(ollama_model="qwen3.5:4b")
    return AppController(_FakeConfigStore(settings))


def test_hotkey_press_runs_recorder_start_on_main_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = _build_controller()
    seen: dict[str, QThread] = {}

    monkeypatch.setattr(
        controller,
        "_get_asr",
        lambda: SimpleNamespace(is_model_available=lambda: True),
    )

    def fake_start() -> None:
        seen["thread"] = QThread.currentThread()

    monkeypatch.setattr(controller.recorder, "start", fake_start)

    worker = threading.Thread(target=controller._on_hotkey_pressed)
    worker.start()
    worker.join()

    _wait_until(lambda: "thread" in seen)

    assert seen["thread"] is controller.thread()
    assert controller._is_recording is True


def test_hotkey_release_runs_recorder_stop_on_main_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = _build_controller()
    seen: dict[str, QThread] = {}
    controller._is_recording = True

    tmp = NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    def fake_stop_and_dump_wav() -> Path:
        seen["thread"] = QThread.currentThread()
        controller.recorder._last_duration_s = 0.0
        controller.recorder._last_rms = 0.0
        return tmp_path

    monkeypatch.setattr(controller.recorder, "stop_and_dump_wav", fake_stop_and_dump_wav)

    worker = threading.Thread(target=controller._on_hotkey_released)
    worker.start()
    worker.join()

    _wait_until(lambda: "thread" in seen)

    assert seen["thread"] is controller.thread()
    assert controller._is_recording is False


def test_wake_guard_rebuilds_when_hotkey_health_check_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _build_controller()
    controller._is_recording = False
    controller._is_processing = False
    controller._last_wake_guard_tick_ts = time.monotonic() - 1.0
    controller.settings.wake_guard_gap_threshold_s = 20.0

    events: list[str] = []
    rebuilds: list[str] = []
    telemetry: list[float] = []

    class _DeadHotkey:
        def ensure_active(self) -> bool:
            return False

    controller.hotkey = _DeadHotkey()  # type: ignore[assignment]
    monkeypatch.setattr(controller.status_signal, "emit", lambda msg: events.append(msg))
    monkeypatch.setattr(controller, "_start_hotkey", lambda: rebuilds.append("rebuilt"))
    monkeypatch.setattr(controller, "_record_wake_guard_rebuild", lambda now: telemetry.append(now))

    controller._on_wake_guard_tick()

    assert rebuilds == ["rebuilt"]
    assert len(telemetry) == 1
    assert events and "health check failed" in events[-1]


def test_update_custom_llm_prompt_persists_without_service_rebuild() -> None:
    controller = _build_controller()
    rebuild_calls: list[str] = []
    updated_settings: list[AppSettings] = []

    controller.settings_updated.connect(lambda s: updated_settings.append(s))
    controller._rebuild_services = lambda: rebuild_calls.append("rebuild")  # type: ignore[method-assign]

    controller.update_custom_llm_prompt("custom prompt")

    assert controller.settings.custom_llm_prompt == "custom prompt"
    assert rebuild_calls == []
    assert updated_settings and updated_settings[-1].custom_llm_prompt == "custom prompt"
