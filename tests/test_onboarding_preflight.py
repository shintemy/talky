from __future__ import annotations

from unittest.mock import patch


def test_recommended_model_constant_exists():
    from talky.models import RECOMMENDED_OLLAMA_MODEL

    assert isinstance(RECOMMENDED_OLLAMA_MODEL, str)
    assert len(RECOMMENDED_OLLAMA_MODEL) > 0


def test_default_ollama_model_uses_recommended_constant():
    from talky.models import RECOMMENDED_OLLAMA_MODEL, AppSettings

    settings = AppSettings()
    assert settings.ollama_model == RECOMMENDED_OLLAMA_MODEL


def test_is_ollama_installed_returns_true_when_found():
    from talky.permissions import is_ollama_installed

    with patch("talky.permissions.shutil.which", return_value="/usr/local/bin/ollama"):
        assert is_ollama_installed() is True


def test_is_ollama_installed_returns_false_when_missing():
    from talky.permissions import is_ollama_installed

    with patch("talky.permissions.shutil.which", return_value=None):
        assert is_ollama_installed() is False
