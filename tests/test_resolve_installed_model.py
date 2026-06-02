from __future__ import annotations

from unittest.mock import patch

from talky.models import resolve_installed_model


def test_keeps_configured_when_installed() -> None:
    with patch("talky.models.list_ollama_models", return_value=["qwen3.5:9b", "gemma4:e2b"]):
        assert resolve_installed_model("qwen3.5:9b") == "qwen3.5:9b"


def test_adopts_other_when_configured_missing() -> None:
    with patch("talky.models.list_ollama_models", return_value=["gemma4:e2b"]):
        assert resolve_installed_model("qwen3.5:9b") == "gemma4:e2b"


def test_keeps_configured_when_no_models() -> None:
    with patch("talky.models.list_ollama_models", return_value=[]):
        assert resolve_installed_model("qwen3.5:9b") == "qwen3.5:9b"


def test_adopts_first_when_configured_empty() -> None:
    with patch("talky.models.list_ollama_models", return_value=["gemma4:e2b", "x:1b"]):
        assert resolve_installed_model("") == "gemma4:e2b"
