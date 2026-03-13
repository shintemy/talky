from __future__ import annotations

import importlib
import sys
import types


def _load_llm_service_with_fake_ollama(chat_impl):
    fake_ollama = types.SimpleNamespace(chat=chat_impl, generate=lambda **kwargs: None)
    sys.modules["ollama"] = fake_ollama
    sys.modules.pop("talky.llm_service", None)
    return importlib.import_module("talky.llm_service")


def test_clean_uses_content_stream_when_available() -> None:
    def chat_impl(**kwargs):  # noqa: ANN003
        del kwargs
        return [
            {"message": {"content": "整理后", "thinking": "internal"}},
            {"message": {"content": "文本", "thinking": ""}},
        ]

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")

    result = cleaner.clean(raw_text="原始文本", dictionary_terms=[])

    assert result == "整理后文本"


def test_clean_never_returns_thinking_fallback() -> None:
    def chat_impl(**kwargs):  # noqa: ANN003
        del kwargs
        return [
            {"message": {"content": "", "thinking": "建议你先..."}},
            {"message": {"content": "", "thinking": "再优化..."}},
        ]

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")

    result = cleaner.clean(raw_text="你来操作", dictionary_terms=[])

    assert result == "你来操作"
