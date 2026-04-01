from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QDialog

from talky.config_store import AppConfigStore
from talky.onboarding import OllamaStatus


def test_ensure_local_wizard_rejected_exits(tmp_path):
    from talky.startup_gate import ensure_local_ollama_ready

    store = AppConfigStore(tmp_path / "settings.json")

    with (
        patch("talky.onboarding.run_preflight_check", return_value=OllamaStatus.NO_MODEL),
        patch("talky.onboarding.OnboardingWizard") as mock_wiz_cls,
    ):
        mock_wiz_cls.return_value.exec.return_value = QDialog.DialogCode.Rejected
        assert ensure_local_ollama_ready(store) is False


def test_ensure_local_already_ready(tmp_path):
    from talky.startup_gate import ensure_local_ollama_ready

    store = AppConfigStore(tmp_path / "settings.json")

    with patch("talky.onboarding.run_preflight_check", return_value=OllamaStatus.READY):
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
    with patch("talky.onboarding.run_preflight_check") as mock_check:
        assert alert_if_local_ollama_unready(store) is False
    mock_check.assert_not_called()


def test_alert_local_skips_when_ollama_ready(tmp_path):
    from talky.startup_gate import alert_if_local_ollama_unready

    store = AppConfigStore(tmp_path / "settings.json")
    with patch("talky.onboarding.run_preflight_check", return_value=OllamaStatus.READY):
        assert alert_if_local_ollama_unready(store) is False


def test_ensure_local_existing_user_missing_bound_model_enters_returning_prompt(tmp_path):
    from talky.startup_gate import ensure_local_ollama_ready

    store = AppConfigStore(tmp_path / "settings.json")
    settings = store.load()
    settings.ollama_model = "qwen3.5:9b"
    store.save(settings)

    with (
        patch(
            "talky.onboarding.run_preflight_check",
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
