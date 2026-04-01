from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from talky.onboarding import OllamaStatus
from talky.startup_gate import _build_unready_local_prompt


def test_local_mode_not_running_prefers_start_local_ollama() -> None:
    title, body, show_remote, show_download, show_open = _build_unready_local_prompt(
        status=OllamaStatus.NOT_RUNNING,
        mode="local",
        host="http://127.0.0.1:11434",
        zh=False,
    )
    assert "local Ollama" in title
    assert "ollama serve" in body
    assert show_remote is False
    assert show_download is False
    assert show_open is True


def test_remote_mode_not_running_prefers_remote_reconfig() -> None:
    title, body, show_remote, show_download, show_open = _build_unready_local_prompt(
        status=OllamaStatus.NOT_RUNNING,
        mode="remote",
        host="http://192.168.1.10:11434",
        zh=False,
    )
    assert "remote Ollama" in title
    assert "remote Ollama is running" in body
    assert show_remote is True
    assert show_download is False
    assert show_open is False
