from __future__ import annotations

import importlib
import sys
import types

import pytest


def _load_llm_service_with_fake_ollama(chat_impl, generate_impl=None):
    if generate_impl is None:
        generate_impl = lambda **kwargs: None  # noqa: E731, ANN001

    def _client_factory(host=None):  # noqa: ANN001
        return types.SimpleNamespace(chat=chat_impl, generate=generate_impl)

    fake_ollama = types.SimpleNamespace(Client=_client_factory)
    sys.modules["ollama"] = fake_ollama
    sys.modules.pop("talky.llm_service", None)
    return importlib.import_module("talky.llm_service")


def test_clean_splits_on_channel_marker_takes_answer_only() -> None:
    """Gemma 4's <channel|> separates thinking from answer. Only the answer should survive."""
    bad = (
        "The user is asking for advice on naming a TTS product.\n"
        "Plan:\n1. Identify the core question.\n"
        "2. Clean up the phrasing.\n"
        "<channel|>如果我想给这个产品命名，是叫 Mockingbird 好，还是叫鹦鹉更好呢？"
    )

    def chat_impl(**kwargs):  # noqa: ANN003
        del kwargs
        return [{"message": {"content": bad, "thinking": ""}}]

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")
    source = "如果是想命名的话TTS的产品应该命名成Mockingbird还是鹦鹉比较好"

    result = cleaner.clean(raw_text=source, dictionary_terms=[])

    assert "The user is" not in result
    assert "Plan:" not in result
    assert "<channel" not in result
    assert "Mockingbird" in result
    assert "鹦鹉" in result


def test_clean_splits_on_channel_marker_simple_case() -> None:
    bad = (
        "The user input is \"你好\".\nThis is a simple greeting.\n"
        "<channel|>你好"
    )

    def chat_impl(**kwargs):  # noqa: ANN003
        del kwargs
        return [{"message": {"content": bad, "thinking": ""}}]

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")

    result = cleaner.clean(raw_text="你好你好你好你好你好你好你好", dictionary_terms=[])

    assert result == "你好"


def test_clean_no_channel_marker_passes_through() -> None:
    """Without <channel|>, output passes through unchanged (no false-positive stripping)."""
    mixed = "OK let me explain this concept.然后我们再来看下一步。"

    def chat_impl(**kwargs):  # noqa: ANN003
        del kwargs
        return [{"message": {"content": mixed, "thinking": ""}}]

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")

    result = cleaner.clean(raw_text="OK let me explain 然后我们再来看下一步", dictionary_terms=[])

    assert "OK let me explain" in result
    assert "然后我们再来看下一步" in result


def test_clean_strips_control_tokens_without_channel_marker() -> None:
    bad = "整理后<|think|>文本"

    def chat_impl(**kwargs):  # noqa: ANN003
        del kwargs
        return [{"message": {"content": bad, "thinking": ""}}]

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")

    result = cleaner.clean(raw_text="原始文本", dictionary_terms=[])

    assert "<|think|>" not in result
    assert "整理后" in result
    assert "文本" in result


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


def test_clean_is_silent_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    def chat_impl(**kwargs):  # noqa: ANN003
        del kwargs
        return [
            {"message": {"content": "整理后", "thinking": "internal"}},
            {"message": {"content": "文本", "thinking": ""}},
        ]

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")

    result = cleaner.clean(raw_text="原始文本", dictionary_terms=[])

    captured = capsys.readouterr()
    assert result == "整理后文本"
    assert captured.out == ""


def test_clean_prints_stream_when_debug_enabled(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def chat_impl(**kwargs):  # noqa: ANN003
        del kwargs
        return [
            {"message": {"content": "整理后", "thinking": "internal"}},
            {"message": {"content": "文本", "thinking": ""}},
        ]

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy", debug_stream=True)

    result = cleaner.clean(raw_text="原始文本", dictionary_terms=[])

    captured = capsys.readouterr()
    assert result == "整理后文本"
    assert "internal" in captured.out
    assert "整理后文本" in captured.out


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


def test_warm_up_uses_short_chat_request() -> None:
    captured = {}

    def chat_impl(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return {"message": {"content": "ok"}}

    def generate_impl(**kwargs):  # noqa: ANN003
        del kwargs
        raise AssertionError("warm_up should not use ollama.generate")

    llm_service = _load_llm_service_with_fake_ollama(chat_impl, generate_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")
    cleaner.warm_up()

    assert captured["model"] == "dummy"
    assert captured["think"] is False
    assert captured["stream"] is False
    assert captured["messages"] == [{"role": "user", "content": "ping"}]


def test_clean_falls_back_to_http_when_sdk_chat_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def chat_impl(**kwargs):  # noqa: ANN003
        del kwargs
        raise RuntimeError("sdk unavailable")

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")
    monkeypatch.setattr(
        cleaner,
        "_chat_via_http",
        lambda **kwargs: [  # noqa: ANN003
            {"message": {"content": "fallback result", "thinking": ""}}
        ],
    )

    result = cleaner.clean(raw_text="原始文本", dictionary_terms=[])

    assert result == "fallback result"


def test_rewrite_selected_text_uses_selected_text_and_instruction() -> None:
    captured = {}

    def chat_impl(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return [{"message": {"content": "我周五去找你", "thinking": ""}}]

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")

    result = cleaner.rewrite_selected_text(
        selected_text="我周四去找你",
        instruction="周四改成周五",
        dictionary_terms=[],
    )

    assert result == "我周五去找你"
    assert captured["stream"] is True
    assert captured["messages"][1]["content"].count("<selected_text>") == 1
    assert "我周四去找你" in captured["messages"][1]["content"]
    assert "周四改成周五" in captured["messages"][1]["content"]


def test_rewrite_selected_text_falls_back_to_selected_text_when_empty_output() -> None:
    def chat_impl(**kwargs):  # noqa: ANN003
        del kwargs
        return [{"message": {"content": "", "thinking": "internal only"}}]

    llm_service = _load_llm_service_with_fake_ollama(chat_impl)
    cleaner = llm_service.OllamaTextCleaner(model_name="dummy")

    result = cleaner.rewrite_selected_text(
        selected_text="我周四去找你",
        instruction="周四改成周五",
        dictionary_terms=[],
    )

    assert result == "我周四去找你"
