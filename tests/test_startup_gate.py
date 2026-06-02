from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QDialog

from talky.config_store import AppConfigStore
from talky.onboarding import OllamaStatus


def test_ensure_local_wizard_rejected_exits(tmp_path, monkeypatch):
    from talky.startup_gate import ensure_local_ollama_ready

    store = AppConfigStore(tmp_path / "settings.json")
    settings = store.load()
    settings.usage_mode = "vibecoding"
    monkeypatch.setattr(store, "load", lambda: settings)

    with (
        patch("talky.startup_gate.run_preflight_check", return_value=OllamaStatus.NO_MODEL),
        patch("talky.onboarding.OnboardingWizard") as mock_wiz_cls,
    ):
        mock_wiz_cls.return_value.exec.return_value = QDialog.DialogCode.Rejected
        assert ensure_local_ollama_ready(store) is False


def test_ensure_local_already_ready(tmp_path, monkeypatch):
    from talky.startup_gate import ensure_local_ollama_ready

    store = AppConfigStore(tmp_path / "settings.json")
    settings = store.load()
    settings.usage_mode = "vibecoding"
    monkeypatch.setattr(store, "load", lambda: settings)

    with patch("talky.startup_gate.run_preflight_check", return_value=OllamaStatus.READY):
        assert ensure_local_ollama_ready(store) is True


def test_ensure_cloud_ready_when_local_mode(tmp_path):
    from talky.startup_gate import ensure_cloud_ready

    store = AppConfigStore(tmp_path / "settings.json")
    assert ensure_cloud_ready(store) is True


def test_alert_local_skips_cloud_mode(tmp_path):
    from talky.startup_gate import alert_if_local_ollama_unready

    store = AppConfigStore(tmp_path / "settings.json")
    s = store.load()
    s.mode = "cloud"
    store.save(s)
    with patch("talky.startup_gate.run_preflight_check") as mock_check:
        assert alert_if_local_ollama_unready(store) is False
    mock_check.assert_not_called()


def test_alert_local_skips_when_ollama_ready(tmp_path):
    from talky.startup_gate import alert_if_local_ollama_unready

    store = AppConfigStore(tmp_path / "settings.json")
    settings = store.load()
    settings.usage_mode = "vibecoding"
    store.save(settings)
    with patch("talky.startup_gate.run_preflight_check", return_value=OllamaStatus.READY):
        assert alert_if_local_ollama_unready(store) is False


def test_alert_skips_when_installed_model_differs_from_configured(tmp_path, monkeypatch):
    from talky.startup_gate import alert_if_local_ollama_unready

    store = AppConfigStore(tmp_path / "settings.json")
    settings = store.load()
    settings.mode = "local"
    settings.usage_mode = "vibecoding"
    settings.ollama_model = "qwen3.5:9b"
    # store.save() resets usage_mode to "daily"; patch load() to keep vibecoding so
    # the LLM-required path actually reaches preflight.
    monkeypatch.setattr(store, "load", lambda: settings)

    # Ollama installed + reachable; only gemma4 is installed (NOT the configured qwen3.5).
    # resolve_installed_model should adopt gemma4 -> preflight READY -> no warning dialog.
    with (
        patch("talky.preflight.is_ollama_installed", return_value=True),
        patch("talky.preflight.check_ollama_reachable", return_value=(True, "")),
        patch("talky.preflight.list_ollama_models", return_value=["gemma4:e2b"]),
        patch("talky.models.list_ollama_models", return_value=["gemma4:e2b"]),
        patch("talky.startup_gate.QMessageBox") as mock_box,
    ):
        result = alert_if_local_ollama_unready(store)

    assert result is False
    mock_box.assert_not_called()


def test_ensure_local_existing_user_missing_bound_model_enters_returning_prompt(tmp_path, monkeypatch):
    from talky.startup_gate import ensure_local_ollama_ready

    store = AppConfigStore(tmp_path / "settings.json")
    settings = store.load()
    settings.usage_mode = "vibecoding"
    settings.ollama_model = "qwen3.5:9b"
    store.config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(store, "load", lambda: settings)

    with (
        patch(
            "talky.startup_gate.run_preflight_check",
            side_effect=[OllamaStatus.NO_MODEL, OllamaStatus.READY],
        ) as mock_preflight,
        patch("talky.onboarding.show_returning_user_prompt", return_value=True) as mock_prompt,
    ):
        assert ensure_local_ollama_ready(store) is True

    assert mock_prompt.call_count == 1
    called_kwargs = mock_prompt.call_args.kwargs
    assert called_kwargs["expected_model"] == "qwen3.5:9b"
    # startup preflight + post-prompt recheck should both enforce required_model
    for call in mock_preflight.call_args_list:
        assert call.kwargs["required_model"] == "qwen3.5:9b"


def test_ensure_local_ollama_ready_skips_daily_mode(tmp_path):
    from talky.startup_gate import ensure_local_ollama_ready

    store = AppConfigStore(tmp_path / "settings.json")
    settings = store.load()
    settings.usage_mode = "daily"
    store.save(settings)

    with patch(
        "talky.startup_gate.run_preflight_check",
        return_value=OllamaStatus.READY,
    ) as mock_preflight:
        assert ensure_local_ollama_ready(store) is True

    mock_preflight.assert_not_called()


def test_alert_if_local_ollama_unready_skips_daily_mode(tmp_path):
    from talky.startup_gate import alert_if_local_ollama_unready

    store = AppConfigStore(tmp_path / "settings.json")
    settings = store.load()
    settings.usage_mode = "daily"
    store.save(settings)

    with patch(
        "talky.startup_gate.run_preflight_check",
        return_value=OllamaStatus.READY,
    ) as mock_preflight:
        assert alert_if_local_ollama_unready(store) is False

    mock_preflight.assert_not_called()


def test_alert_if_local_ollama_unready_uses_runtime_usage_mode_override(tmp_path):
    from talky.startup_gate import alert_if_local_ollama_unready

    store = AppConfigStore(tmp_path / "settings.json")
    settings = store.load()
    settings.usage_mode = "daily"
    store.save(settings)

    with patch(
        "talky.startup_gate.run_preflight_check",
        return_value=OllamaStatus.READY,
    ) as mock_preflight:
        assert alert_if_local_ollama_unready(store, usage_mode="translation") is False

    mock_preflight.assert_called_once()


def test_controller_resets_usage_mode_to_daily_on_startup():
    from talky.controller import AppController
    from talky.models import AppSettings

    settings = AppSettings(usage_mode="translation", ollama_model="qwen3.5:4b")

    class _FakeConfigStore:
        def load(self) -> AppSettings:
            return settings

        def save(self, updated: AppSettings) -> None:
            settings.__dict__.update(updated.__dict__)

    controller = AppController(_FakeConfigStore())

    assert controller.settings.usage_mode == "daily"
