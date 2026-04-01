from __future__ import annotations

import enum
import locale

from talky.models import list_ollama_models
from talky.permissions import check_ollama_reachable, is_ollama_installed


class OllamaStatus(enum.Enum):
    READY = "ready"
    NOT_INSTALLED = "not_installed"
    NOT_RUNNING = "not_running"
    NO_MODEL = "no_model"


def run_preflight_check(required_model: str = "") -> OllamaStatus:
    """Check Ollama install/service/model availability without any UI dependency."""
    installed = is_ollama_installed()
    reachable, _ = check_ollama_reachable()
    if not installed and not reachable:
        return OllamaStatus.NOT_INSTALLED
    if not reachable:
        return OllamaStatus.NOT_RUNNING
    models = list_ollama_models()
    if not models:
        return OllamaStatus.NO_MODEL
    required = (required_model or "").strip()
    if required and required not in models:
        return OllamaStatus.NO_MODEL
    return OllamaStatus.READY


def detect_system_locale() -> str:
    """Return 'zh' for Chinese system locale, otherwise 'en'."""
    try:
        lang, _ = locale.getlocale()
        if lang and lang.startswith("zh"):
            return "zh"
    except Exception:
        pass
    return "en"
