from talky.models import AppSettings
from talky.prompting import (
    DEFAULT_LLM_PROMPT_TEMPLATE,
    LEGACY_DEFAULT_LLM_PROMPT_TEMPLATE_NO_TYPOGRAPHY,
    LEGACY_DEFAULT_LLM_PROMPT_TEMPLATE_V044,
)


def test_from_dict_clears_legacy_builtin_prompt_snapshots() -> None:
    for template in (
        DEFAULT_LLM_PROMPT_TEMPLATE,
        LEGACY_DEFAULT_LLM_PROMPT_TEMPLATE_V044,
        LEGACY_DEFAULT_LLM_PROMPT_TEMPLATE_NO_TYPOGRAPHY,
    ):
        loaded = AppSettings.from_dict({"custom_llm_prompt": template})
        assert loaded.custom_llm_prompt == ""


def test_from_dict_keeps_real_custom_prompt() -> None:
    custom = "My strict custom prompt with team-specific rules"
    loaded = AppSettings.from_dict({"custom_llm_prompt": custom})
    assert loaded.custom_llm_prompt == custom
