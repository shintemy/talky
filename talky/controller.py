from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import gc
import os
import re
import shutil
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import sounddevice as sd
from PyQt6.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal, pyqtSlot

from talky.config_store import AppConfigStore
from talky.debug_log import append_debug_log
from talky.dictionary_corrector import apply_phonetic_dictionary, normalize_person_pronouns
from talky.dictionary_entries import (
    extract_person_terms,
    extract_terms,
    match_dictionary_tags,
    parse_dictionary_entries,
)
from talky.focus import FrontAppInfo, activate_app_by_pid, get_frontmost_app, has_focus_target
from talky.hotkey import HoldToTalkHotkey
from talky.history_store import HistoryStore
from talky.llm_service import OllamaTextCleaner
from talky.models import (
    AppSettings,
    SESSION_START_USAGE_MODE,
    list_ollama_models,
    resolve_installed_model,
)
from talky.paster import ClipboardPaster
from talky.permissions import check_ollama_reachable
from talky.prompting import build_asr_initial_prompt, build_asr_strict_retry_prompt
from talky.processing_guard import (
    estimate_asr_timeout_seconds,
    estimate_processing_timeout_seconds,
    should_timeout_processing,
)
from talky.recorder import AudioRecorder
from talky.remote_service import CloudProcessService
from talky.semantic_edit import looks_like_edit_instruction
from talky.task_timeout import run_with_timeout
from talky.text_guard import (
    collapse_duplicate_output,
    enforce_pronoun_consistency,
    enforce_source_boundaries,
    strip_trailing_asr_translation_hallucination,
    looks_like_unexpected_english_asr_output,
    looks_like_wrong_translation_output,
)
from talky.periodic_maintenance import should_run_periodic_maintenance
from talky.wake_guard import (
    normalize_wake_guard_threshold,
    should_recover_stale_recording_after_wake,
    should_mark_suspected_false_positive,
    should_rebuild_hotkey,
)
from talky.warmup_policy import should_warm_up_asr
from talky.weekly_summary import (
    is_week_summarized,
    previous_iso_week_range,
    run_weekly_summary,
)
from talky.obsidian_export import ExportResult, run_export

if TYPE_CHECKING:
    from talky.asr_service import MlxWhisperASR

_OPENCC_SIMPLIFIER = None
_MIN_RECORD_DURATION_S = 0.30
_MIN_RECORD_RMS = 0.003
_HOTKEY_COOLDOWN_S = 0.45
_WAKE_GUARD_INTERVAL_MS = 5000
_PERIODIC_MAINTENANCE_INTERVAL_S = 6 * 3600
_WEEKLY_SUMMARY_CHECK_INTERVAL_S = 30 * 60
_PROCESSING_WATCHDOG_INTERVAL_MS = 1000
_RECORD_RELEASE_GUARD_INTERVAL_MS = 250
_PROCESSING_TIMEOUT_S = 45.0
_ASR_STEP_TIMEOUT_S = 35.0
_LLM_STEP_TIMEOUT_S = 25.0
_AUDIO_FINALIZE_TIMEOUT_S = 8.0
_TRANSIENT_FRONT_APPS = {
    "finder",
    "dock",
    "loginwindow",
    "textinputmenuagent",
    "systemuiserver",
    "controlcenter",
    "notificationcenter",
}


@dataclass(frozen=True)
class ProcessingResult:
    final_text: str
    raw_text: str = ""


def normalize_to_simplified_chinese(text: str) -> str:
    global _OPENCC_SIMPLIFIER
    if not text:
        return text
    if _OPENCC_SIMPLIFIER is None:
        try:
            from opencc import OpenCC
        except Exception:
            return text
        _OPENCC_SIMPLIFIER = OpenCC("t2s")
    try:
        return _OPENCC_SIMPLIFIER.convert(text)
    except Exception:
        return text


def looks_like_repetitive_asr_hallucination(text: str) -> bool:
    value = text.strip()
    if len(value) < 120:
        return False
    lower = value.lower()
    words = re.findall(r"[a-zA-Z']+", lower)
    if len(words) < 24:
        return False
    # Detect pathological loops like:
    # "means of the finalistic means of the finalistic ..."
    for size in (3, 4, 5):
        max_start = len(words) - (size * 6)
        if max_start < 0:
            continue
        for i in range(max_start + 1):
            chunk = words[i : i + size]
            repeats = 1
            j = i + size
            while j + size <= len(words) and words[j : j + size] == chunk:
                repeats += 1
                j += size
            if repeats >= 6:
                return True
    return False


class AppController(QObject):
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    pipeline_state_signal = pyqtSignal(str)
    settings_updated = pyqtSignal(object)
    show_result_popup_signal = pyqtSignal(str)
    show_settings_window_signal = pyqtSignal()
    # Paste on main thread only (worker emits); macOS + pynput need this.
    paste_to_front_signal = pyqtSignal(str)
    hotkey_action_signal = pyqtSignal(str)

    def __init__(self, config_store: AppConfigStore) -> None:
        super().__init__()
        self.config_store = config_store
        self.settings = self.config_store.load()
        self.settings.usage_mode = SESSION_START_USAGE_MODE
        self._apply_ollama_host_env()

        self.recorder = AudioRecorder(
            sample_rate=self.settings.sample_rate,
            channels=self.settings.channels,
        )
        self._asr: MlxWhisperASR | None = None
        self.llm = OllamaTextCleaner(
            model_name=self.settings.ollama_model,
            debug_stream=self.settings.llm_debug_stream,
        )
        self.paster = ClipboardPaster(paste_delay_ms=self.settings.auto_paste_delay_ms)
        self.history_store = HistoryStore(Path.home() / ".talky" / "history")
        # Keep user history persistent across app upgrades/re-installs.
        legacy_dirs = [
            Path(__file__).resolve().parent.parent / "history",
            Path.cwd() / "history",
        ]
        self.history_store.migrate_from(legacy_dirs)
        self.cloud_service: CloudProcessService | None = self._build_cloud_service()

        self.paste_to_front_signal.connect(
            self._do_paste_to_front,
            Qt.ConnectionType.QueuedConnection,
        )
        self.hotkey_action_signal.connect(
            self._handle_hotkey_action,
            Qt.ConnectionType.QueuedConnection,
        )

        self._is_processing = False
        self._is_recording = False
        self.hotkey: HoldToTalkHotkey | None = None
        self._last_output_text = ""
        self._last_output_ts = 0.0
        self._hotkey_cooldown_until_ts = 0.0
        self._wake_guard_timer: QTimer | None = None
        self._last_wake_guard_tick_ts = time.monotonic()
        self._last_wake_guard_rebuild_ts = 0.0
        self._last_periodic_maintenance_ts = time.monotonic()
        self._summaries_dir = Path.home() / ".talky" / "summaries"
        self._last_weekly_summary_check_ts = 0.0
        self._weekly_summary_in_progress = False
        self._last_pipeline_state = "idle"
        self._processing_watchdog_timer: QTimer | None = None
        self._record_release_guard_timer: QTimer | None = None
        self._processing_started_ts = 0.0
        self._processing_timeout_s = _PROCESSING_TIMEOUT_S
        self._processing_generation = 0
        self._processing_wav_path: Path | None = None
        self._last_target_front_app: FrontAppInfo | None = None
        self._last_focus_target_pid: int | None = None

    def _get_asr(self) -> MlxWhisperASR:
        if self.is_cloud_mode:
            raise RuntimeError("Local ASR is not used in cloud mode.")
        if self._asr is None:
            from talky.asr_service import MlxWhisperASR

            self._asr = MlxWhisperASR(
                model_name=self.settings.whisper_model,
                language=self.settings.language,
            )
            return self._asr
        # Defensive sync: if runtime settings changed but service rebuild was missed
        # (e.g. UI save timing edge), always force ASR instance to match latest settings.
        if (
            getattr(self._asr, "model_name", "") != self.settings.whisper_model
            or getattr(self._asr, "language", "") != self.settings.language
        ):
            from talky.asr_service import MlxWhisperASR

            self._asr = MlxWhisperASR(
                model_name=self.settings.whisper_model,
                language=self.settings.language,
            )
        return self._asr

    @pyqtSlot(str)
    def _do_paste_to_front(self, text: str) -> None:
        self.paster.paste_text(text)

    def start(self) -> None:
        self._start_hotkey()
        self._start_wake_guard()
        self._start_processing_watchdog()
        self._start_record_release_guard()
        self._last_periodic_maintenance_ts = time.monotonic()
        self._emit_pipeline_state("idle", source="start")
        self._warm_up_models_async()

    def request_show_settings(self) -> None:
        self.show_settings_window_signal.emit()

    def refresh_hotkey_listener(self) -> None:
        """Recreate global hotkey listener after permission state changes."""
        self._start_hotkey()

    def stop(self) -> None:
        if self._record_release_guard_timer is not None:
            self._record_release_guard_timer.stop()
            self._record_release_guard_timer = None
        if self._processing_watchdog_timer is not None:
            self._processing_watchdog_timer.stop()
            self._processing_watchdog_timer = None
        if self._wake_guard_timer is not None:
            self._wake_guard_timer.stop()
            self._wake_guard_timer = None
        if self.hotkey:
            self.hotkey.stop()
            self.hotkey = None

    def update_settings(self, new_settings: AppSettings) -> None:
        previous = self.settings
        self.settings = new_settings
        self._apply_ollama_host_env()
        self.config_store.save(new_settings)
        if self._settings_require_service_rebuild(previous, new_settings):
            self._rebuild_services()
        if self._hotkey_config_changed(previous, new_settings) or self.hotkey is None:
            self._start_hotkey()
        self.settings_updated.emit(new_settings)
        self.status_signal.emit("Settings saved.")

    @staticmethod
    def _hotkey_config_changed(previous: AppSettings, current: AppSettings) -> bool:
        return (
            previous.hotkey != current.hotkey
            or list(previous.custom_hotkey) != list(current.custom_hotkey)
        )

    @staticmethod
    def _settings_require_service_rebuild(previous: AppSettings, current: AppSettings) -> bool:
        # Rebuild runtime services only when their constructor/runtime dependencies changed.
        keys = (
            "sample_rate",
            "channels",
            "auto_paste_delay_ms",
            "whisper_model",
            "language",
            "ollama_model",
            "llm_debug_stream",
            "mode",
            "cloud_api_url",
            "cloud_api_key",
            "ollama_host",
            "usage_mode",
        )
        return any(getattr(previous, key) != getattr(current, key) for key in keys)

    def update_dictionary(self, lines: list[str]) -> None:
        """Update just the dictionary portion of settings."""
        settings = self._load_persisted_settings_preserving_session_mode()
        settings.custom_dictionary = lines
        self.config_store.save(settings)
        self.settings = settings
        self.settings_updated.emit(settings)

    def _load_persisted_settings_preserving_session_mode(self) -> AppSettings:
        settings = self.config_store.load()
        settings.usage_mode = self.settings.usage_mode
        return settings

    def update_custom_llm_prompt(self, prompt: str, *, emit_settings_updated: bool = True) -> None:
        """Persist prompt text without rebuilding recorder/LLM services."""
        normalized = (prompt or "").strip()
        if self.settings.custom_llm_prompt == normalized:
            return
        self.settings.custom_llm_prompt = normalized
        self.config_store.save(self.settings)
        if emit_settings_updated:
            self.settings_updated.emit(self.settings)

    def update_custom_vibe_prompt(self, prompt: str, *, emit_settings_updated: bool = True) -> None:
        """Persist vibecoding prompt text without rebuilding recorder/LLM services."""
        normalized = (prompt or "").strip()
        if self.settings.custom_vibe_prompt == normalized:
            return
        self.settings.custom_vibe_prompt = normalized
        self.config_store.save(self.settings)
        if emit_settings_updated:
            self.settings_updated.emit(self.settings)

    def _build_cloud_service(self) -> CloudProcessService | None:
        if not self._usage_mode_requires_llm(self.settings.usage_mode):
            return None
        if (
            self.settings.mode == "cloud"
            and self.settings.cloud_api_url
            and self.settings.cloud_api_key
        ):
            return CloudProcessService(
                api_url=self.settings.cloud_api_url,
                api_key=self.settings.cloud_api_key,
            )
        return None

    @property
    def is_cloud_mode(self) -> bool:
        return (
            self._usage_mode_requires_llm(self.settings.usage_mode)
            and self.settings.mode == "cloud"
            and self.cloud_service is not None
        )

    def _rebuild_services(self) -> None:
        self._apply_ollama_host_env()
        self.recorder = AudioRecorder(
            sample_rate=self.settings.sample_rate,
            channels=self.settings.channels,
        )
        self._asr = None
        self.llm = OllamaTextCleaner(
            model_name=self.settings.ollama_model,
            debug_stream=self.settings.llm_debug_stream,
        )
        self.paster = ClipboardPaster(paste_delay_ms=self.settings.auto_paste_delay_ms)
        self.cloud_service = self._build_cloud_service()

    def _apply_ollama_host_env(self) -> None:
        host = (self.settings.ollama_host or "http://127.0.0.1:11434").strip().rstrip("/")
        if not host:
            host = "http://127.0.0.1:11434"
        os.environ["OLLAMA_HOST"] = host

    def _is_talky_front_app(self, front_app: FrontAppInfo | None) -> bool:
        if front_app is None:
            return False
        name = front_app.name.strip().lower()
        if "talky" in name:
            return True
        if front_app.pid == os.getpid():
            return True
        return False

    def _is_transient_front_app(self, front_app: FrontAppInfo | None) -> bool:
        if front_app is None:
            return True
        name = front_app.name.strip().lower()
        return name in _TRANSIENT_FRONT_APPS

    def _remember_target_front_app(self, front_app: FrontAppInfo | None) -> None:
        if front_app is None:
            return
        if front_app.pid <= 0:
            return
        if self._is_talky_front_app(front_app):
            return
        if self._is_transient_front_app(front_app):
            # Transient system UI (TextInputMenuAgent, SystemUIServer, etc.) must not
            # become the paste target; keep the previously-remembered real front app so
            # _should_paste_to_focus_target can restore focus to it.
            return
        self._last_target_front_app = front_app

    def _should_paste_to_focus_target(self, current_front_app: FrontAppInfo | None) -> bool:
        self._remember_target_front_app(current_front_app)
        if has_focus_target(current_front_app):
            return True
        if (
            self._last_focus_target_pid is not None
            and current_front_app is not None
            and current_front_app.pid == self._last_focus_target_pid
        ):
            # AX focus detection can briefly report false negatives on some apps.
            return True
        candidate = self._last_target_front_app
        if candidate is None:
            return False
        if not (
            self._is_talky_front_app(current_front_app)
            or self._is_transient_front_app(current_front_app)
        ):
            return False
        if not activate_app_by_pid(candidate.pid):
            return False
        # Allow AX focus attributes to catch up after app activation.
        time.sleep(0.06)
        restored = get_frontmost_app()
        self._remember_target_front_app(restored)
        return has_focus_target(restored)

    def _is_local_ollama_host(self, host: str) -> bool:
        value = (host or "").strip()
        if not value:
            return True
        parsed = urlparse(value if "://" in value else f"http://{value}")
        hostname = (parsed.hostname or "").lower()
        return hostname in {"127.0.0.1", "localhost", "::1"}

    def _build_ollama_unreachable_error(self, base_error: str) -> str:
        host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        if self._is_local_ollama_host(host):
            guide = (
                "\nRun: ollama serve and ensure model exists: "
                + self.settings.ollama_model
            )
        else:
            guide = (
                "\nCheck remote Ollama host and model on: "
                + host
                + "\nExpected model: "
                + self.settings.ollama_model
            )
        return base_error + guide

    @staticmethod
    def _usage_mode_requires_llm(usage_mode: str) -> bool:
        return usage_mode in {"vibecoding", "translation"}

    def _start_hotkey(self) -> None:
        if self.hotkey:
            self.hotkey.stop()
        self.hotkey = HoldToTalkHotkey(
            key_mode=self.settings.hotkey,
            custom_keys=self.settings.custom_hotkey,
            on_press=self._on_hotkey_pressed,
            on_release=self._on_hotkey_released,
        )
        self.hotkey.start()
        append_debug_log(
            "hotkey listener started: "
            f"configured={self.settings.hotkey}; fallback={self.hotkey.using_fallback}"
        )
        QTimer.singleShot(350, self._notify_hotkey_status_after_start)
        self._last_wake_guard_tick_ts = time.monotonic()

    def _start_wake_guard(self) -> None:
        if self._wake_guard_timer is not None:
            self._wake_guard_timer.stop()
        timer = QTimer(self)
        timer.setInterval(_WAKE_GUARD_INTERVAL_MS)
        timer.timeout.connect(self._on_wake_guard_tick)
        timer.start()
        self._wake_guard_timer = timer
        self._last_wake_guard_tick_ts = time.monotonic()

    def _wake_guard_threshold(self) -> float:
        return normalize_wake_guard_threshold(self.settings.wake_guard_gap_threshold_s)

    def _record_wake_guard_rebuild(self, now_ts: float) -> None:
        self.settings.wake_guard_rebuild_count += 1
        if should_mark_suspected_false_positive(
            last_rebuild_ts=self._last_wake_guard_rebuild_ts,
            now_ts=now_ts,
        ):
            self.settings.wake_guard_suspected_false_positive_count += 1
        self._last_wake_guard_rebuild_ts = now_ts
        self.config_store.save(self.settings)

    def _on_wake_guard_tick(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_wake_guard_tick_ts
        self._last_wake_guard_tick_ts = now
        if not self._is_recording and not self._is_processing:
            self._maybe_run_periodic_maintenance(now)
            self._maybe_run_weekly_summary(now)
        threshold = self._wake_guard_threshold()
        rebuild_due_to_gap = should_rebuild_hotkey(elapsed, threshold)
        hotkey_healthy = bool(self.hotkey and self.hotkey.ensure_active())
        if not rebuild_due_to_gap and hotkey_healthy:
            return
        recovered_stale_recording = False
        if should_recover_stale_recording_after_wake(
            elapsed_seconds=elapsed,
            threshold_seconds=threshold,
            is_recording=self._is_recording,
        ):
            recovered_stale_recording = self._recover_stale_recording_after_wake()
        if self._is_recording or self._is_processing:
            return
        # System sleep/wake often invalidates global key taps; proactively rebuild.
        self._start_hotkey()
        self._record_wake_guard_rebuild(now)
        if recovered_stale_recording:
            reason = "System wake detected; stale recording discarded."
        elif rebuild_due_to_gap:
            reason = "System wake detected."
        else:
            reason = "Hotkey listener health check failed."
        self.status_signal.emit(
            f"{reason} Hotkey listener refreshed. "
            f"Wake-guard telemetry: {self.settings.wake_guard_suspected_false_positive_count}/"
            f"{self.settings.wake_guard_rebuild_count} suspected false-positive."
        )

    def _maybe_run_periodic_maintenance(self, now_ts: float) -> None:
        elapsed = now_ts - self._last_periodic_maintenance_ts
        if not should_run_periodic_maintenance(
            elapsed_since_last_s=elapsed,
            interval_s=_PERIODIC_MAINTENANCE_INTERVAL_S,
            is_recording=self._is_recording,
            is_processing=self._is_processing,
        ):
            return
        self._run_periodic_maintenance(now_ts)

    def _run_periodic_maintenance(self, now_ts: float) -> None:
        append_debug_log("periodic maintenance: clearing runtime cache and refreshing hotkey")
        had_asr = self._asr is not None
        self._asr = None
        collected = gc.collect()
        self._start_hotkey()
        self._last_periodic_maintenance_ts = now_ts
        append_debug_log(
            "periodic maintenance done: "
            f"asr_reset={had_asr}; gc_collected={collected}"
        )
        self.status_signal.emit(
            "Routine maintenance completed. Hotkey listener refreshed and runtime cache cleared."
        )

    def _maybe_run_weekly_summary(self, now_ts: float) -> None:
        if self._weekly_summary_in_progress:
            return
        if (now_ts - self._last_weekly_summary_check_ts) < _WEEKLY_SUMMARY_CHECK_INTERVAL_S:
            return
        self._last_weekly_summary_check_ts = now_ts
        from datetime import date

        today = date.today()
        start, end = previous_iso_week_range(today)
        if is_week_summarized(self._summaries_dir, start, end):
            return
        self._weekly_summary_in_progress = True
        worker = threading.Thread(
            target=self._run_weekly_summary_async,
            args=(today,),
            daemon=True,
        )
        worker.start()

    def _weekly_summary_is_ready(self) -> bool:
        if self.is_cloud_mode:
            return False
        if self.settings.mode not in {"local", "remote"}:
            return False
        models = list_ollama_models(os.environ.get("OLLAMA_HOST", ""))
        return bool(models) and self.settings.ollama_model in models

    def _run_weekly_summary_async(self, today) -> None:
        try:
            path = run_weekly_summary(
                today=today,
                summaries_dir=self._summaries_dir,
                read_structured=self.history_store.read_structured_entries,
                summarize=lambda content, system_prompt: self.llm.summarize(
                    content, system_prompt=system_prompt
                ),
                is_ready=self._weekly_summary_is_ready,
                should_abort=lambda: self._is_recording or self._is_processing,
                ui_locale=self.settings.ui_locale,
                model_name=self.settings.ollama_model,
                now_text=datetime.now().strftime("%Y-%m-%d %H:%M"),
                log=append_debug_log,
            )
            if path is not None:
                self.status_signal.emit(f"Weekly summary generated: {path}")
        except Exception as exc:
            append_debug_log("weekly summary worker failed", exc=exc)
        finally:
            self._weekly_summary_in_progress = False

    def export_weekly_summaries_to_obsidian(self) -> ExportResult:
        """Sync all weekly summaries into the configured Obsidian vault."""
        return run_export(self.settings, self._summaries_dir)

    def _recover_stale_recording_after_wake(self) -> bool:
        append_debug_log("wake guard recovering stale recording after sleep/wake gap")
        try:
            stream, _chunks, _sample_rate = self.recorder.stop_and_detach()
        except Exception as exc:
            append_debug_log("wake guard failed to detach stale recording", exc=exc)
            self._is_recording = False
            self._emit_pipeline_state("idle", source="wake_guard_recording_recover_error")
            return False
        try:
            self.recorder._safe_close_stream(stream)
        except Exception as exc:
            append_debug_log("wake guard failed to close stale recording stream", exc=exc)
        self._is_recording = False
        self._emit_pipeline_state("idle", source="wake_guard_stale_recording")
        return True

    def _start_processing_watchdog(self) -> None:
        if self._processing_watchdog_timer is not None:
            self._processing_watchdog_timer.stop()
        timer = QTimer(self)
        timer.setInterval(_PROCESSING_WATCHDOG_INTERVAL_MS)
        timer.timeout.connect(self._on_processing_watchdog_tick)
        timer.start()
        self._processing_watchdog_timer = timer

    def _start_record_release_guard(self) -> None:
        if self._record_release_guard_timer is not None:
            self._record_release_guard_timer.stop()
        timer = QTimer(self)
        timer.setInterval(_RECORD_RELEASE_GUARD_INTERVAL_MS)
        timer.timeout.connect(self._on_record_release_guard_tick)
        timer.start()
        self._record_release_guard_timer = timer

    def _on_record_release_guard_tick(self) -> None:
        if not self._is_recording:
            return
        hotkey = self.hotkey
        if hotkey is None:
            return
        try:
            pressed_now = hotkey.is_pressed_now()
        except Exception:
            return
        if pressed_now:
            return
        append_debug_log("record release guard: synthesized release after missed hotkey event")
        self._handle_hotkey_released_main_thread()

    def _on_processing_watchdog_tick(self) -> None:
        if not self._is_processing or self._processing_started_ts <= 0:
            return
        elapsed = time.monotonic() - self._processing_started_ts
        if not should_timeout_processing(elapsed, self._processing_timeout_s):
            return
        append_debug_log(
            "processing watchdog timeout: "
            f"elapsed={elapsed:.1f}s; timeout={self._processing_timeout_s:.1f}s"
        )
        self._cancel_processing("processing_timeout")
        self.error_signal.emit(
            "Processing timeout. Current task was cancelled. Please retry."
        )

    def _notify_hotkey_status_after_start(self) -> None:
        hotkey = self.hotkey
        if hotkey is None:
            return
        if not hotkey.using_fallback:
            return
        append_debug_log(
            "hotkey fallback active: "
            f"configured={self.settings.hotkey}; runtime_fallback=right_option"
        )
        self.status_signal.emit(
            "Fn hook unavailable on this macOS setup. "
            "Using Right Option as runtime fallback. Hold Right Option to talk."
        )

    def _on_hotkey_pressed(self) -> None:
        self._dispatch_hotkey_action("press")

    def _on_hotkey_released(self) -> None:
        self._dispatch_hotkey_action("release")

    def _dispatch_hotkey_action(self, action: str) -> None:
        if QThread.currentThread() is self.thread():
            self._handle_hotkey_action(action)
            return
        self.hotkey_action_signal.emit(action)

    @pyqtSlot(str)
    def _handle_hotkey_action(self, action: str) -> None:
        if action == "press":
            self._handle_hotkey_pressed_main_thread()
        elif action == "release":
            self._handle_hotkey_released_main_thread()

    def _handle_hotkey_pressed_main_thread(self) -> None:
        if time.monotonic() < self._hotkey_cooldown_until_ts:
            return
        if self._is_processing:
            self._cancel_processing("hotkey_pressed_during_processing")
            return
        if self._is_recording:
            return
        if not self.is_cloud_mode and not self._get_asr().is_model_available():
            self.error_signal.emit("__MODEL_NOT_FOUND__")
            return
        if self._usage_mode_requires_llm(self.settings.usage_mode) and not self.is_cloud_mode:
            ok, error = check_ollama_reachable()
            if not ok:
                self.error_signal.emit(self._build_ollama_unreachable_error(error))
                return
        front_app = get_frontmost_app()
        self._remember_target_front_app(front_app)
        if front_app is not None and has_focus_target(front_app):
            self._last_focus_target_pid = front_app.pid
        else:
            self._last_focus_target_pid = None
        try:
            self.recorder.start()
            self._is_recording = True
            self._emit_pipeline_state("recording", source="hotkey_pressed")
        except sd.PortAudioError as exc:
            self.error_signal.emit(self._format_microphone_portaudio_error(exc))
        except Exception as exc:
            self.error_signal.emit(f"Failed to start recording: {exc}")

    def _handle_hotkey_released_main_thread(self) -> None:
        if not self._is_recording:
            return
        try:
            detached = self.recorder.stop_and_detach()
            self._is_recording = False
            stream, chunks, sample_rate = detached
            append_debug_log(
                "record stop detached: "
                f"chunks={len(chunks)}; sample_rate={sample_rate:.1f}"
            )

            front_app = get_frontmost_app()
            self._remember_target_front_app(front_app)
            has_focus = has_focus_target(front_app)
            if front_app is not None and has_focus:
                self._last_focus_target_pid = front_app.pid

            self._is_processing = True
            self._processing_started_ts = time.monotonic()
            self._processing_timeout_s = _PROCESSING_TIMEOUT_S
            if self._processing_watchdog_timer is None or not self._processing_watchdog_timer.isActive():
                self._start_processing_watchdog()
            self._processing_generation += 1
            generation = self._processing_generation
            self._emit_pipeline_state("processing", source="record_released")
            append_debug_log(
                "processing armed: "
                f"generation={generation}; timeout={self._processing_timeout_s:.1f}s"
            )

            worker = threading.Thread(
                target=self._process_pipeline,
                args=(detached, generation, has_focus),
                daemon=True,
            )
            worker.start()
        except Exception as exc:
            self._is_recording = False
            self._is_processing = False
            self._processing_started_ts = 0.0
            self._processing_timeout_s = _PROCESSING_TIMEOUT_S
            self._emit_pipeline_state("idle", source="record_stop_error")
            self.error_signal.emit(f"Failed to stop recording: {exc}")
        finally:
            self._hotkey_cooldown_until_ts = time.monotonic() + _HOTKEY_COOLDOWN_S

    def _cancel_processing(self, source: str) -> None:
        # Invalidate current task so stale worker completion won't overwrite state.
        self._processing_generation += 1
        self._is_processing = False
        self._processing_started_ts = 0.0
        self._processing_timeout_s = _PROCESSING_TIMEOUT_S
        append_debug_log(f"processing cancelled: source={source}")
        self._emit_pipeline_state("idle", source=source)
        wav_path = self._processing_wav_path
        self._processing_wav_path = None
        if wav_path is not None:
            try:
                wav_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _process_cloud(self, wav_path: Path) -> str:
        assert self.cloud_service is not None
        dict_terms = extract_terms(
            parse_dictionary_entries(self.settings.custom_dictionary)
        )
        cloud_start = time.perf_counter()
        final_text = self.cloud_service.process(
            audio_path=wav_path,
            dictionary=dict_terms,
            language=self.settings.language,
        )
        cloud_elapsed = time.perf_counter() - cloud_start
        print(f"[Talky] Cloud elapsed: {cloud_elapsed:.2f}s")
        final_text = normalize_to_simplified_chinese(final_text)
        return final_text

    def _transcribe_with_language_guard(
        self,
        wav_path: Path,
        *,
        asr_prompt: str,
        asr_timeout_s: float,
    ) -> str:
        asr_start = time.perf_counter()
        raw_text = run_with_timeout(
            lambda: self._get_asr().transcribe(wav_path, initial_prompt=asr_prompt),
            asr_timeout_s,
            label="ASR step",
        )
        if looks_like_unexpected_english_asr_output(
            raw_text,
            language=self.settings.language,
        ):
            append_debug_log(
                "ASR language drift suspected: "
                f"lang={self.settings.language!r}; preview={raw_text[:120]!r}; retrying once"
            )
            self._asr = None
            retry_prompt = build_asr_strict_retry_prompt(language=self.settings.language)
            raw_text = run_with_timeout(
                lambda: self._get_asr().transcribe(wav_path, initial_prompt=retry_prompt),
                asr_timeout_s,
                label="ASR retry step",
            )
        asr_elapsed = time.perf_counter() - asr_start
        print(f"[Talky] ASR elapsed: {asr_elapsed:.2f}s")
        append_debug_log(
            f"ASR result: lang={self.settings.language!r}; preview={raw_text[:120]!r}"
        )
        return raw_text

    def _run_llm_for_mode(self, *, corrected_raw_text: str, dict_terms: list[str]) -> str:
        usage_mode = self.settings.usage_mode

        def _call_llm(*, translation_strict_retry: bool = False) -> str:
            return self.llm.clean(
                raw_text=corrected_raw_text,
                dictionary_terms=dict_terms,
                custom_prompt_template=self.settings.custom_llm_prompt,
                usage_mode=usage_mode,
                custom_vibe_template=self.settings.custom_vibe_prompt,
                translation_source_language=self.settings.language,
                translation_output_language=self.settings.translation_output_language,
                translation_strict_retry=translation_strict_retry,
            )

        final_text = run_with_timeout(
            lambda: _call_llm(),
            _LLM_STEP_TIMEOUT_S,
            label="LLM step",
        )
        if usage_mode != "translation":
            return final_text

        target = self.settings.translation_output_language
        if looks_like_wrong_translation_output(
            final_text,
            target_language=target,
            source_text=corrected_raw_text,
        ):
            append_debug_log(
                "Translation target mismatch; retrying once: "
                f"target={target!r}; preview={final_text[:120]!r}"
            )
            final_text = run_with_timeout(
                lambda: _call_llm(translation_strict_retry=True),
                _LLM_STEP_TIMEOUT_S,
                label="LLM translation retry step",
            )
        if looks_like_wrong_translation_output(
            final_text,
            target_language=target,
            source_text=corrected_raw_text,
        ):
            raise RuntimeError(
                f"Translation output did not match target language ({target}). Please retry."
            )
        append_debug_log(
            f"Translation result: target={target!r}; preview={final_text[:120]!r}"
        )
        if target == "zh":
            final_text = normalize_to_simplified_chinese(final_text)
        return final_text

    def _process_local(
        self,
        wav_path: Path,
        *,
        asr_timeout_s: float,
        selected_text_snapshot: str = "",
    ) -> ProcessingResult:
        dictionary_entries = parse_dictionary_entries(self.settings.custom_dictionary)
        dict_terms = extract_terms(dictionary_entries)
        person_terms = extract_person_terms(dictionary_entries)
        asr_prompt = build_asr_initial_prompt(
            dict_terms,
            language=self.settings.language,
        )
        raw_text = self._transcribe_with_language_guard(
            wav_path,
            asr_prompt=asr_prompt,
            asr_timeout_s=asr_timeout_s,
        )
        if not raw_text:
            raise RuntimeError("ASR returned empty text. Please retry.")
        corrected_raw_text = apply_phonetic_dictionary(raw_text, dict_terms)
        if len(corrected_raw_text.replace(" ", "").strip()) < 2:
            return ProcessingResult(final_text="", raw_text=raw_text)
        if looks_like_repetitive_asr_hallucination(corrected_raw_text):
            raise RuntimeError(
                "ASR output appears unstable (repetitive loop). "
                "Please retry in a quieter environment."
            )

        if self.settings.usage_mode == "daily":
            daily_text = strip_trailing_asr_translation_hallucination(
                corrected_raw_text,
                self.settings.language,
            )
            daily_text = normalize_to_simplified_chinese(daily_text)
            daily_text = collapse_duplicate_output(daily_text)
            return ProcessingResult(final_text=daily_text, raw_text=raw_text)

        ok, error = check_ollama_reachable()
        if not ok:
            raise RuntimeError(self._build_ollama_unreachable_error(error))

        if (
            selected_text_snapshot
            and looks_like_edit_instruction(corrected_raw_text)
            and self.settings.usage_mode != "translation"
        ):
            rewritten_text = run_with_timeout(
                lambda: self.llm.rewrite_selected_text(
                    selected_text=selected_text_snapshot,
                    instruction=corrected_raw_text,
                    dictionary_terms=dict_terms,
                ),
                _LLM_STEP_TIMEOUT_S,
                label="LLM selection-rewrite step",
            )
            rewritten_text = apply_phonetic_dictionary(rewritten_text, dict_terms)
            rewritten_text = normalize_person_pronouns(rewritten_text, person_terms)
            rewritten_text = collapse_duplicate_output(rewritten_text)
            rewritten_text = normalize_to_simplified_chinese(rewritten_text)
            return ProcessingResult(final_text=rewritten_text)

        llm_start = time.perf_counter()
        final_text = self._run_llm_for_mode(
            corrected_raw_text=corrected_raw_text,
            dict_terms=dict_terms,
        )
        llm_elapsed = time.perf_counter() - llm_start
        print(f"[Talky] LLM elapsed: {llm_elapsed:.2f}s")
        if self.settings.usage_mode == "vibecoding":
            final_text = apply_phonetic_dictionary(final_text, dict_terms)
            final_text = normalize_person_pronouns(final_text, person_terms)
            final_text = enforce_pronoun_consistency(corrected_raw_text, final_text)
            final_text = enforce_source_boundaries(corrected_raw_text, final_text)
            final_text = normalize_to_simplified_chinese(final_text)
        final_text = collapse_duplicate_output(final_text)
        return ProcessingResult(final_text=final_text, raw_text=raw_text)

    def _compute_history_tags(self, final_text: str) -> tuple[list[str], list[str]]:
        entries = parse_dictionary_entries(self.settings.custom_dictionary)
        return match_dictionary_tags(final_text, entries)

    def _process_pipeline(
        self,
        detached: tuple,
        generation: int,
        has_focus: bool,
    ) -> None:
        stream, chunks, sample_rate = detached
        wav_path: Path | None = None
        try:
            append_debug_log(
                "pipeline worker begin: "
                f"generation={generation}; chunks={len(chunks)}; sample_rate={sample_rate:.1f}; "
                f"has_focus={has_focus}"
            )
            if generation != self._processing_generation:
                self.recorder._safe_close_stream(stream)
                return

            wav_path, duration_s, rms = run_with_timeout(
                lambda: self.recorder.close_and_dump_wav(
                    stream,
                    chunks,
                    sample_rate,
                ),
                _AUDIO_FINALIZE_TIMEOUT_S,
                label="audio finalize step",
            )
            append_debug_log(
                "audio finalize done: "
                f"duration={duration_s:.2f}s; rms={rms:.5f}"
            )

            if duration_s < _MIN_RECORD_DURATION_S:
                wav_path.unlink(missing_ok=True)
                wav_path = None
                return
            if rms < _MIN_RECORD_RMS:
                wav_path.unlink(missing_ok=True)
                wav_path = None
                return

            asr_timeout_s = max(_ASR_STEP_TIMEOUT_S, estimate_asr_timeout_seconds(duration_s))
            self._processing_timeout_s = max(
                _PROCESSING_TIMEOUT_S,
                estimate_processing_timeout_seconds(
                    duration_s,
                    llm_timeout_seconds=_LLM_STEP_TIMEOUT_S,
                ),
            )
            append_debug_log(
                "processing timeout policy: "
                f"audio_duration={duration_s:.2f}s; asr_timeout={asr_timeout_s:.1f}s; "
                f"overall_timeout={self._processing_timeout_s:.1f}s"
            )
            self._processing_wav_path = wav_path
            debug_audio_path = self._persist_debug_audio_if_enabled(wav_path)

            selected_text_snapshot = ""
            if has_focus:
                try:
                    selected_text_snapshot = run_with_timeout(
                        self.paster.capture_selected_text,
                        3.0,
                        label="capture_selected_text",
                    )
                except Exception:
                    selected_text_snapshot = ""

            if generation != self._processing_generation:
                return
            if self.is_cloud_mode:
                result = ProcessingResult(final_text=self._process_cloud(wav_path))
            else:
                result = self._process_local(
                    wav_path,
                    asr_timeout_s=asr_timeout_s,
                    selected_text_snapshot=selected_text_snapshot,
                )
            final_text = result.final_text
            raw_text = result.raw_text
            if generation != self._processing_generation:
                return
            if not final_text:
                return

            now = time.monotonic()
            if final_text == self._last_output_text and (now - self._last_output_ts) < 1.2:
                return
            self._last_output_text = final_text
            self._last_output_ts = now

            print(f"[Talky] Final text: {final_text}")
            matched_persons, matched_terms = self._compute_history_tags(final_text)
            history_path = self.history_store.append(
                final_text,
                raw_text=raw_text,
                usage_mode=self.settings.usage_mode,
                asr_language=self.settings.language,
                translation_output_language=self.settings.translation_output_language,
                debug_audio_path=debug_audio_path,
                matched_persons=matched_persons,
                matched_terms=matched_terms,
            )
            print(f"[Talky] History appended: {history_path}")

            current_front_app = get_frontmost_app()
            if self._should_paste_to_focus_target(current_front_app):
                self.paste_to_front_signal.emit(final_text)
            else:
                self.show_result_popup_signal.emit(final_text)
        except FileNotFoundError as exc:
            if "Whisper model path not found" in str(exc):
                self.error_signal.emit("__MODEL_NOT_FOUND__")
            else:
                self.error_signal.emit(f"Processing failed: {exc}")
        except Exception as exc:
            self.error_signal.emit(f"Processing failed: {exc}")
        finally:
            if generation == self._processing_generation:
                self._is_processing = False
                self._processing_started_ts = 0.0
                self._processing_timeout_s = _PROCESSING_TIMEOUT_S
                self._processing_wav_path = None
                self._emit_pipeline_state("idle", source="pipeline_finally")
            if wav_path is not None:
                try:
                    wav_path.unlink(missing_ok=True)
                except Exception:
                    pass

    def _persist_debug_audio_if_enabled(self, source_wav: Path) -> Path | None:
        from talky.feature_flags import debug_ui_enabled

        if not debug_ui_enabled() or not self.settings.debug_audio_enabled:
            return None
        try:
            output_dir = Path.home() / ".talky" / "debug-audio"
            output_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            if self.settings.usage_mode == "translation":
                target = output_dir / (
                    f"{ts}-mode_{self.settings.usage_mode}-asr_{self.settings.language}"
                    f"-target_{self.settings.translation_output_language}.wav"
                )
            else:
                target = output_dir / (
                    f"{ts}-mode_{self.settings.usage_mode}-asr_{self.settings.language}.wav"
                )
            shutil.copy2(source_wav, target)

            max_files = max(1, min(int(self.settings.debug_audio_max_files), 500))
            wav_files = sorted(
                output_dir.glob("*.wav"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for stale in wav_files[max_files:]:
                stale.unlink(missing_ok=True)

            append_debug_log(f"debug audio saved: {target}")
            return target
        except Exception as exc:
            append_debug_log(f"debug audio save failed: {exc}")
            return None

    def _emit_pipeline_state(self, state: str, *, source: str) -> None:
        previous = self._last_pipeline_state
        self._last_pipeline_state = state
        append_debug_log(
            "pipeline_state_emit: "
            f"{previous}->{state}; source={source}; "
            f"is_recording={self._is_recording}; is_processing={self._is_processing}; "
            f"hotkey={self.settings.hotkey}"
        )
        self.pipeline_state_signal.emit(state)

    def _format_microphone_portaudio_error(self, exc: sd.PortAudioError) -> str:
        message = str(exc)
        lowered = message.lower()
        if "-9986" in lowered or "device unavailable" in lowered:
            return (
                "Cannot start microphone: input device is unavailable or busy. "
                "Check System Settings > Sound > Input, or close other apps using the mic, then retry.\n"
                f"Details: {exc}"
            )
        return (
            "Cannot start microphone. Grant access at "
            "System Settings > Privacy & Security > Microphone.\n"
            f"Details: {exc}"
        )

    def _auto_adopt_installed_model(self) -> None:
        """If the configured Ollama model isn't installed but others are, adopt an installed one."""
        if self.is_cloud_mode:
            return
        if self.settings.mode not in {"local", "remote"}:
            return
        host = os.environ.get("OLLAMA_HOST", "")
        resolved = resolve_installed_model(self.settings.ollama_model, host)
        if not resolved or resolved == self.settings.ollama_model:
            return
        append_debug_log(
            f"auto-adopt installed ollama model: {self.settings.ollama_model!r} -> {resolved!r}"
        )
        self.settings.ollama_model = resolved
        self.config_store.save(self.settings)
        self.llm = OllamaTextCleaner(
            model_name=resolved, debug_stream=self.settings.llm_debug_stream
        )
        self.settings_updated.emit(self.settings)

    def _warm_up_models_async(self) -> None:
        if self.is_cloud_mode:
            return
        if should_warm_up_asr():
            from talky.asr_service import mark_asr_warm_up_pending

            mark_asr_warm_up_pending()
        worker = threading.Thread(target=self._warm_up_models, daemon=True)
        worker.start()

    def _warm_up_models(self) -> None:
        try:
            self._auto_adopt_installed_model()
        except Exception as exc:
            append_debug_log(f"auto-adopt model failed: {exc}")
        try:
            if should_warm_up_asr():
                try:
                    warm_asr_start = time.perf_counter()
                    self._get_asr().warm_up()
                    warm_asr_elapsed = time.perf_counter() - warm_asr_start
                    print(f"[Talky] Whisper warm-up done: {warm_asr_elapsed:.2f}s")
                except Exception as exc:
                    print(f"[Talky] Whisper warm-up failed: {exc}")
            else:
                append_debug_log("Whisper warm-up skipped at startup (TALKY_ASR_WARMUP not enabled).")

            if not self._usage_mode_requires_llm(self.settings.usage_mode):
                append_debug_log("LLM warm-up skipped at startup (usage mode does not need LLM).")
                return

            try:
                warm_llm_start = time.perf_counter()
                self.llm.warm_up()
                warm_llm_elapsed = time.perf_counter() - warm_llm_start
                print(f"[Talky] Ollama warm-up done: {warm_llm_elapsed:.2f}s")
            except Exception as exc:
                print(f"[Talky][debug] Ollama warm-up skipped: {exc}")
        finally:
            from talky.asr_service import mark_asr_warm_up_complete

            mark_asr_warm_up_complete()
