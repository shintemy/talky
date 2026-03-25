from __future__ import annotations

import enum
import locale

from talky.models import detect_ollama_model
from talky.permissions import check_ollama_reachable, is_ollama_installed


class OllamaStatus(enum.Enum):
    READY = "ready"
    NOT_INSTALLED = "not_installed"
    NOT_RUNNING = "not_running"
    NO_MODEL = "no_model"


def run_preflight_check() -> OllamaStatus:
    """Check Ollama installation, service, and model availability."""
    if not is_ollama_installed():
        reachable, _ = check_ollama_reachable()
        if not reachable:
            return OllamaStatus.NOT_INSTALLED
    reachable, _ = check_ollama_reachable()
    if not reachable:
        return OllamaStatus.NOT_RUNNING
    if not detect_ollama_model():
        return OllamaStatus.NO_MODEL
    return OllamaStatus.READY


def detect_system_locale() -> str:
    """Return 'zh' if macOS system language is Chinese, else 'en'."""
    try:
        lang, _ = locale.getdefaultlocale()
        if lang and lang.startswith("zh"):
            return "zh"
    except Exception:
        pass
    return "en"
