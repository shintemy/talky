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

import talky.controller as controller_module
from talky.controller import AppController
from talky.focus import FrontAppInfo
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


def test_hotkey_press_llm_mode_blocks_when_ollama_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _build_controller()
    controller.settings.usage_mode = "vibecoding"
    recorder_starts: list[str] = []
    errors: list[str] = []

    monkeypatch.setattr(
        controller,
        "_get_asr",
        lambda: SimpleNamespace(is_model_available=lambda: True),
    )
    monkeypatch.setattr(
        "talky.controller.check_ollama_reachable",
        lambda: (False, "Ollama service unavailable: test"),
    )
    monkeypatch.setattr(controller.recorder, "start", lambda: recorder_starts.append("start"))
    controller.error_signal.connect(lambda msg: errors.append(msg))

    controller._handle_hotkey_pressed_main_thread()

    assert recorder_starts == []
    assert errors and "Ollama service unavailable: test" in errors[-1]


def test_hotkey_release_detach_runs_on_main_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """stop_and_detach (non-blocking) must run on the main Qt thread."""
    controller = _build_controller()
    seen: dict[str, QThread] = {}
    controller._is_recording = True

    fake_stream = SimpleNamespace(stop=lambda: None, close=lambda: None)

    def fake_stop_and_detach():
        seen["thread"] = QThread.currentThread()
        return fake_stream, [], 16000.0

    monkeypatch.setattr(controller.recorder, "stop_and_detach", fake_stop_and_detach)
    monkeypatch.setattr(
        controller.recorder,
        "close_and_dump_wav",
        lambda *a, **kw: (Path("/dev/null"), 0.0, 0.0),
    )

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
    # Keep the idle-tick weekly-summary check from firing real background work;
    # this test only exercises hotkey health-check recovery.
    controller._last_weekly_summary_check_ts = time.monotonic()
    controller.settings.wake_guard_gap_threshold_s = 20.0

    events: list[str] = []
    rebuilds: list[str] = []
    telemetry: list[float] = []

    class _DeadHotkey:
        def ensure_active(self) -> bool:
            return False

    controller.hotkey = _DeadHotkey()  # type: ignore[assignment]
    # PyQt6 signals are read-only on .emit; connect a slot instead of patching emit.
    controller.status_signal.connect(events.append)
    monkeypatch.setattr(controller, "_start_hotkey", lambda: rebuilds.append("rebuilt"))
    monkeypatch.setattr(controller, "_record_wake_guard_rebuild", lambda now: telemetry.append(now))

    controller._on_wake_guard_tick()

    assert rebuilds == ["rebuilt"]
    assert len(telemetry) == 1
    assert events and "health check failed" in events[-1]


def test_wake_guard_recovers_stale_recording_after_sleep_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _build_controller()
    controller._is_recording = True
    controller._is_processing = False
    controller._last_wake_guard_tick_ts = time.monotonic() - 60.0
    controller.settings.wake_guard_gap_threshold_s = 20.0
    events: list[str] = []
    rebuilds: list[str] = []
    telemetry: list[float] = []
    closed_streams: list[object] = []
    fake_stream = object()

    monkeypatch.setattr(
        controller.recorder,
        "stop_and_detach",
        lambda: (fake_stream, [], 16000.0),
    )
    monkeypatch.setattr(
        controller.recorder,
        "_safe_close_stream",
        lambda stream: closed_streams.append(stream),
    )
    # PyQt6 signals are read-only on .emit; connect a slot instead of patching emit.
    controller.status_signal.connect(events.append)
    monkeypatch.setattr(controller, "_start_hotkey", lambda: rebuilds.append("rebuilt"))
    monkeypatch.setattr(controller, "_record_wake_guard_rebuild", lambda now: telemetry.append(now))

    controller._on_wake_guard_tick()

    assert controller._is_recording is False
    assert controller._last_pipeline_state == "idle"
    assert closed_streams == [fake_stream]
    assert rebuilds == ["rebuilt"]
    assert len(telemetry) == 1
    assert events and "stale recording" in events[-1]


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


def test_refresh_hotkey_listener_restarts_hotkey() -> None:
    controller = _build_controller()
    calls: list[str] = []
    controller._start_hotkey = lambda: calls.append("restart")  # type: ignore[method-assign]

    controller.refresh_hotkey_listener()

    assert calls == ["restart"]


def test_update_settings_hotkey_only_skips_service_rebuild_and_warmup() -> None:
    controller = _build_controller()
    rebuild_calls: list[str] = []
    warmup_calls: list[str] = []
    hotkey_restart_calls: list[str] = []

    controller._rebuild_services = lambda: rebuild_calls.append("rebuild")  # type: ignore[method-assign]
    controller._warm_up_models_async = lambda: warmup_calls.append("warmup")  # type: ignore[method-assign]
    controller._start_hotkey = lambda: hotkey_restart_calls.append("hotkey")  # type: ignore[method-assign]

    updated = AppSettings(**controller.settings.to_dict())
    updated.hotkey = "right_option"

    controller.update_settings(updated)

    assert rebuild_calls == []
    assert warmup_calls == []
    assert hotkey_restart_calls == ["hotkey"]


def test_hotkey_fallback_does_not_persist_override() -> None:
    controller = _build_controller()
    controller.settings.hotkey = "fn"
    controller.hotkey = SimpleNamespace(using_fallback=True)  # type: ignore[assignment]
    seen: list[AppSettings] = []
    controller.settings_updated.connect(lambda s: seen.append(s))

    controller._notify_hotkey_status_after_start()

    assert controller.settings.hotkey == "fn"
    assert seen == []


def test_record_release_guard_synthesizes_release_when_key_not_pressed() -> None:
    controller = _build_controller()
    controller._is_recording = True
    calls: list[str] = []
    controller.hotkey = SimpleNamespace(is_pressed_now=lambda: False)  # type: ignore[assignment]
    controller._handle_hotkey_released_main_thread = (  # type: ignore[method-assign]
        lambda: calls.append("released")
    )

    controller._on_record_release_guard_tick()

    assert calls == ["released"]


def test_should_paste_after_refocus_from_talky(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = _build_controller()
    controller._last_target_front_app = FrontAppInfo(name="Safari", pid=321)

    monkeypatch.setattr("talky.controller.activate_app_by_pid", lambda pid: pid == 321)
    monkeypatch.setattr(
        "talky.controller.get_frontmost_app",
        lambda: FrontAppInfo(name="Safari", pid=321),
    )
    monkeypatch.setattr("talky.controller.has_focus_target", lambda app: app.name == "Safari")
    monkeypatch.setattr("talky.controller.time.sleep", lambda _s: None)

    assert controller._should_paste_to_focus_target(FrontAppInfo(name="Talky", pid=111))


def test_should_paste_after_refocus_from_transient_front_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _build_controller()
    controller._last_target_front_app = FrontAppInfo(name="Safari", pid=321)

    monkeypatch.setattr("talky.controller.activate_app_by_pid", lambda pid: pid == 321)
    monkeypatch.setattr(
        "talky.controller.get_frontmost_app",
        lambda: FrontAppInfo(name="Safari", pid=321),
    )
    monkeypatch.setattr("talky.controller.has_focus_target", lambda app: app.pid == 321)
    monkeypatch.setattr("talky.controller.time.sleep", lambda _s: None)

    assert controller._should_paste_to_focus_target(
        FrontAppInfo(name="TextInputMenuAgent", pid=777)
    )


def test_cancel_processing_resets_timeout_budget() -> None:
    controller = _build_controller()
    controller._is_processing = True
    controller._processing_started_ts = 123.0
    controller._processing_timeout_s = 215.0

    controller._cancel_processing("unit_test")

    assert controller._is_processing is False
    assert controller._processing_started_ts == 0.0
    assert controller._processing_timeout_s == controller_module._PROCESSING_TIMEOUT_S


def test_process_pipeline_applies_timeout_to_audio_finalize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _build_controller()
    controller._processing_generation = 7
    controller._is_processing = True
    labels: list[str] = []

    def fake_run_with_timeout(func, timeout_s: float, *, label: str):  # noqa: ANN001
        del timeout_s
        labels.append(label)
        return func()

    monkeypatch.setattr("talky.controller.run_with_timeout", fake_run_with_timeout)

    with NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)

    monkeypatch.setattr(
        controller.recorder,
        "close_and_dump_wav",
        lambda *_args, **_kwargs: (wav_path, 1.2, 0.01),
    )
    monkeypatch.setattr(controller, "_process_local", lambda *_args, **_kwargs: "")

    controller._process_pipeline((object(), [], 16000.0), generation=7, has_focus=False)

    assert "audio finalize step" in labels


def test_process_pipeline_stores_raw_text_but_pastes_final_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _build_controller()
    controller._processing_generation = 9
    controller._is_processing = True
    history_entries: list[tuple[str, str]] = []
    pasted: list[str] = []

    with NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)

    monkeypatch.setattr(
        controller.recorder,
        "close_and_dump_wav",
        lambda *_args, **_kwargs: (wav_path, 1.2, 0.01),
    )
    monkeypatch.setattr(
        controller,
        "_process_local",
        lambda *_args, **_kwargs: SimpleNamespace(
            final_text="LLM 最终输出",
            raw_text="Whisper 原文",
        ),
    )
    monkeypatch.setattr(controller, "_should_paste_to_focus_target", lambda _app: True)
    monkeypatch.setattr("talky.controller.get_frontmost_app", lambda: None)
    monkeypatch.setattr(
        controller.history_store,
        "append",
        lambda text, raw_text="", **_kwargs: history_entries.append((text, raw_text))
        or Path("/tmp/history.md"),
    )
    # PyQt6 signals are read-only on .emit. Replace the real (queued) _do_paste_to_front
    # slot with a synchronous test slot so the emitted text is captured immediately and
    # no real paste is queued onto the shared QApplication event loop.
    controller.paste_to_front_signal.disconnect()
    controller.paste_to_front_signal.connect(pasted.append)

    controller._process_pipeline((object(), [], 16000.0), generation=9, has_focus=False)

    assert history_entries == [("LLM 最终输出", "Whisper 原文")]
    assert pasted == ["LLM 最终输出"]


def test_process_local_daily_mode_skips_ollama_and_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _build_controller()
    controller.settings.usage_mode = "daily"
    labels: list[str] = []

    monkeypatch.setattr(
        "talky.controller.check_ollama_reachable",
        lambda: pytest.fail("Daily mode should not check Ollama"),
    )
    monkeypatch.setattr(
        controller,
        "_get_asr",
        lambda: SimpleNamespace(
            transcribe=lambda *_args, **_kwargs: "Whisper 原文",
        ),
    )
    monkeypatch.setattr(
        controller.llm,
        "clean",
        lambda **_kwargs: pytest.fail("LLM clean should not run"),
    )

    def fake_run_with_timeout(func, timeout_s: float, *, label: str):  # noqa: ANN001
        del timeout_s
        labels.append(label)
        return func()

    monkeypatch.setattr("talky.controller.run_with_timeout", fake_run_with_timeout)

    result = controller._process_local(Path("/tmp/input.wav"), asr_timeout_s=3.0)

    assert result.final_text == "Whisper 原文"
    assert result.raw_text == "Whisper 原文"
    assert labels == ["ASR step"]


def test_process_local_daily_mode_normalizes_to_simplified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _build_controller()
    controller.settings.usage_mode = "daily"

    monkeypatch.setattr(
        "talky.controller.check_ollama_reachable",
        lambda: pytest.fail("Daily mode should not check Ollama"),
    )
    monkeypatch.setattr(
        controller,
        "_get_asr",
        lambda: SimpleNamespace(
            transcribe=lambda *_args, **_kwargs: "我應該發現一個bug。",
        ),
    )

    result = controller._process_local(Path("/tmp/input.wav"), asr_timeout_s=3.0)

    assert result.final_text == "我应该发现一个bug。"
    assert result.raw_text == "我應該發現一個bug。"


def test_process_local_daily_mode_strips_trailing_english_translation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _build_controller()
    controller.settings.usage_mode = "daily"
    controller.settings.language = "zh"

    monkeypatch.setattr(
        controller,
        "_get_asr",
        lambda: SimpleNamespace(
            transcribe=lambda *_args, **_kwargs: (
                "来我来说一段话你看一下。Let me say a sentence. Take a look."
            ),
        ),
    )

    result = controller._process_local(Path("/tmp/input.wav"), asr_timeout_s=3.0)

    assert result.final_text == "来我来说一段话你看一下。"
    assert "Let me say" in result.raw_text


def test_process_local_retries_when_asr_drifts_to_english(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _build_controller()
    controller.settings.usage_mode = "daily"
    controller.settings.language = "zh"
    calls: list[str] = []

    def fake_transcribe(_wav_path, initial_prompt: str) -> str:
        calls.append(initial_prompt)
        if len(calls) == 1:
            return "This should be ok, my Chinese output this time is ok"
        return "这次应该没问题，我的中文输出这次是对的"

    monkeypatch.setattr(
        controller,
        "_get_asr",
        lambda: SimpleNamespace(transcribe=fake_transcribe),
    )

    result = controller._process_local(Path("/tmp/input.wav"), asr_timeout_s=3.0)

    assert len(calls) == 2
    assert "中文口述" in calls[1]
    assert "这次应该没问题" in result.final_text


def test_process_local_rejects_repetitive_asr_hallucination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _build_controller()
    controller.settings.usage_mode = "daily"
    repetitive = ("means of the finalistic " * 30).strip()

    monkeypatch.setattr(
        controller,
        "_get_asr",
        lambda: SimpleNamespace(
            transcribe=lambda *_args, **_kwargs: repetitive,
        ),
    )

    with pytest.raises(RuntimeError, match="ASR output appears unstable"):
        controller._process_local(Path("/tmp/input.wav"), asr_timeout_s=3.0)


def test_debug_audio_saved_and_pruned_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    controller = _build_controller()
    controller.settings.debug_audio_enabled = True
    controller.settings.debug_audio_max_files = 2
    controller.settings.usage_mode = "daily"
    controller.settings.language = "zh"

    monkeypatch.setattr(controller_module.Path, "home", lambda: tmp_path)

    src1 = tmp_path / "src1.wav"
    src2 = tmp_path / "src2.wav"
    src3 = tmp_path / "src3.wav"
    src1.write_bytes(b"wav1")
    src2.write_bytes(b"wav2")
    src3.write_bytes(b"wav3")

    controller._persist_debug_audio_if_enabled(src1)
    time.sleep(0.01)
    controller._persist_debug_audio_if_enabled(src2)
    time.sleep(0.01)
    controller._persist_debug_audio_if_enabled(src3)

    saved = sorted((tmp_path / ".talky" / "debug-audio").glob("*.wav"))
    assert len(saved) == 2
    assert all("mode_daily" in p.name for p in saved)


def test_debug_audio_skipped_when_debug_ui_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import talky.feature_flags as feature_flags

    controller = _build_controller()
    controller.settings.debug_audio_enabled = True
    feature_flags.debug_ui_enabled.cache_clear()
    monkeypatch.setattr(feature_flags, "debug_ui_enabled", lambda: False)

    src = tmp_path / "src.wav"
    src.write_bytes(b"wav")

    assert controller._persist_debug_audio_if_enabled(src) is None


def test_get_asr_rebuilds_when_language_drift_detected() -> None:
    controller = _build_controller()
    controller.settings.language = "zh"
    first = controller._get_asr()
    assert first.language == "zh"

    controller.settings.language = "en"
    second = controller._get_asr()
    assert second.language == "en"
    assert second is not first


def test_periodic_maintenance_clears_asr_and_rebuilds_hotkey(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _build_controller()
    controller._asr = object()
    started: list[int] = []

    def fake_start_hotkey() -> None:
        started.append(1)

    monkeypatch.setattr(controller, "_start_hotkey", fake_start_hotkey)
    controller._last_periodic_maintenance_ts = time.monotonic() - (7 * 3600)

    controller._maybe_run_periodic_maintenance(time.monotonic())

    assert controller._asr is None
    assert started == [1]
    assert controller._last_periodic_maintenance_ts > 0


def test_periodic_maintenance_skips_while_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _build_controller()
    controller._asr = object()
    controller._is_processing = True
    started: list[int] = []

    monkeypatch.setattr(controller, "_start_hotkey", lambda: started.append(1))
    controller._last_periodic_maintenance_ts = time.monotonic() - (7 * 3600)

    controller._maybe_run_periodic_maintenance(time.monotonic())

    assert controller._asr is not None
    assert started == []


def test_compute_history_tags_matches_dictionary(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = _build_controller()
    controller.settings.custom_dictionary = ["[person]张三", "Kubernetes"]

    persons, terms = controller._compute_history_tags("张三 部署 Kubernetes")

    assert persons == ["张三"]
    assert terms == ["Kubernetes"]


def test_compute_history_tags_empty_dictionary() -> None:
    controller = _build_controller()
    controller.settings.custom_dictionary = []
    assert controller._compute_history_tags("anything") == ([], [])


from datetime import date


def test_maybe_run_weekly_summary_spawns_worker_when_due(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = _build_controller()
    controller._summaries_dir = tmp_path
    controller._last_weekly_summary_check_ts = 0.0

    called: list = []
    monkeypatch.setattr(
        controller, "_run_weekly_summary_async", lambda today: called.append(today)
    )

    controller._maybe_run_weekly_summary(time.monotonic())
    _wait_until(lambda: len(called) == 1)

    assert controller._weekly_summary_in_progress is True


def test_maybe_run_weekly_summary_skips_when_already_summarized(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from talky.weekly_summary import previous_iso_week_range, summary_path

    controller = _build_controller()
    controller._summaries_dir = tmp_path
    controller._last_weekly_summary_check_ts = 0.0
    start, end = previous_iso_week_range(date.today())
    summary_path(tmp_path, start, end).write_text("done", encoding="utf-8")

    called: list = []
    monkeypatch.setattr(
        controller, "_run_weekly_summary_async", lambda today: called.append(today)
    )

    controller._maybe_run_weekly_summary(time.monotonic())
    time.sleep(0.05)
    _app.processEvents()

    assert called == []
    assert controller._weekly_summary_in_progress is False


def test_maybe_run_weekly_summary_skips_when_in_progress(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = _build_controller()
    controller._summaries_dir = tmp_path
    controller._last_weekly_summary_check_ts = 0.0
    controller._weekly_summary_in_progress = True

    called: list = []
    monkeypatch.setattr(
        controller, "_run_weekly_summary_async", lambda today: called.append(today)
    )

    controller._maybe_run_weekly_summary(time.monotonic())
    assert called == []


def test_run_weekly_summary_async_resets_flag_and_notifies(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = _build_controller()
    controller._summaries_dir = tmp_path
    controller._weekly_summary_in_progress = True

    monkeypatch.setattr(
        "talky.controller.run_weekly_summary",
        lambda **kwargs: tmp_path / "summary-x.md",
    )
    statuses: list[str] = []
    controller.status_signal.connect(statuses.append)

    controller._run_weekly_summary_async(date(2026, 6, 2))
    _app.processEvents()

    assert controller._weekly_summary_in_progress is False
    assert any("summary-x.md" in s for s in statuses)


def test_run_weekly_summary_async_resets_flag_on_error(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = _build_controller()
    controller._summaries_dir = tmp_path
    controller._weekly_summary_in_progress = True

    def boom(**kwargs):
        raise RuntimeError("nope")

    monkeypatch.setattr("talky.controller.run_weekly_summary", boom)

    controller._run_weekly_summary_async(date(2026, 6, 2))
    assert controller._weekly_summary_in_progress is False
