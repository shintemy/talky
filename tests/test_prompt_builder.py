from talky.prompting import (
    DEFAULT_LLM_PROMPT_TEMPLATE,
    VIBECODING_LLM_PROMPT_TEMPLATE,
    build_asr_initial_prompt,
    build_llm_system_prompt,
    build_selection_rewrite_prompt,
    inject_vibe_coding_block,
    strip_vibe_coding_block,
    has_vibe_coding_block,
    VIBE_CODING_PROMPT_BLOCK,
)


def test_build_asr_prompt_contains_dictionary_terms() -> None:
    dictionary = ["MLX", "Qwen", "Alice Chen"]

    prompt = build_asr_initial_prompt(dictionary)

    assert "MLX" in prompt
    assert "Qwen" in prompt
    assert "Alice Chen" in prompt


def test_build_llm_prompt_includes_required_rules() -> None:
    dictionary = ["TensorRT", "Alice Huang"]

    prompt = build_llm_system_prompt(dictionary)

    assert "You are a Dictation Transcription Editor" in prompt
    assert "STRICT LANGUAGE MATCH" in prompt
    assert "NEVER translate" in prompt
    assert "Mixed-language input" in prompt
    assert "STRICT PERSPECTIVE" in prompt
    assert "NO ADDITIONS" in prompt
    assert "PRESERVE SENTENCE TYPE" in prompt
    assert "NEVER generate a conversational" in prompt
    assert "NOISE REDUCTION" in prompt
    assert "HIGH INFORMATION DENSITY" in prompt
    assert "STRUCTURAL REORGANIZATION" in prompt
    assert "Short Question: Output exactly one cleanly formatted question sentence" in prompt
    assert "<TYPOGRAPHY_RULES>" in prompt
    assert "PANGU SPACING (Crucial)" in prompt
    assert "NUMBER SPACING" in prompt
    assert "Strictly use full-width punctuation (，。！？) in Chinese context" in prompt
    assert "<DICTIONARY>" in prompt
    assert "Raw Transcript:" in prompt
    assert "[INSERT_USER_TEXT_HERE]" in prompt
    assert "TensorRT" in prompt
    assert "Alice Huang" in prompt


# ---------------------------------------------------------------------------
# Dual-template: default prompt selection
# ---------------------------------------------------------------------------


def test_build_llm_prompt_daily_uses_default_template() -> None:
    prompt = build_llm_system_prompt(["MLX"], usage_mode="daily")

    assert "STRICT LANGUAGE MATCH" in prompt
    assert "NEVER translate" in prompt
    assert "FORCED ENGLISH OUTPUT" not in prompt
    assert not has_vibe_coding_block(prompt)


def test_build_llm_prompt_vibecoding_uses_dedicated_template() -> None:
    prompt = build_llm_system_prompt(["MLX"], usage_mode="vibecoding")

    assert "FORCED ENGLISH OUTPUT" in prompt
    assert "EXTREME CONCISENESS" in prompt
    assert "VIBE-CENTRIC EDITING" in prompt
    assert "Dictation-to-English Editor" in prompt
    assert "STRICT LANGUAGE MATCH" not in prompt
    assert "NEVER translate" not in prompt
    assert "MLX" in prompt


def test_vibecoding_template_no_chinese_typography() -> None:
    prompt = build_llm_system_prompt([], usage_mode="vibecoding")

    assert "PANGU SPACING (Crucial)" not in prompt
    assert "full-width punctuation" not in prompt
    assert "standard English punctuation" in prompt


def test_vibecoding_template_preserves_structural_constraints() -> None:
    prompt = build_llm_system_prompt([], usage_mode="vibecoding")

    assert "STRICT PERSPECTIVE" in prompt
    assert "NO ADDITIONS" in prompt
    assert "PRESERVE SENTENCE TYPE" in prompt
    assert "Raw Transcript:" in prompt
    assert "<DICTIONARY>" in prompt


# ---------------------------------------------------------------------------
# Custom template + vibecoding: inject + neutralize fallback
# ---------------------------------------------------------------------------


def test_build_llm_prompt_custom_template_vibecoding_injects_block() -> None:
    custom = DEFAULT_LLM_PROMPT_TEMPLATE.replace("{dictionary}", "custom")

    prompt = build_llm_system_prompt(["X"], custom_template=custom, usage_mode="vibecoding")

    assert has_vibe_coding_block(prompt)
    assert "VIBE CODING PROTOCOL" in prompt


def test_build_llm_prompt_custom_template_vibecoding_neutralizes_language() -> None:
    custom = DEFAULT_LLM_PROMPT_TEMPLATE.replace("{dictionary}", "custom")

    prompt = build_llm_system_prompt(["X"], custom_template=custom, usage_mode="vibecoding")

    assert "STRICT LANGUAGE MATCH" not in prompt
    assert "NEVER translate" not in prompt
    assert "ENGLISH OUTPUT" in prompt


def test_build_llm_prompt_custom_template_daily_unchanged() -> None:
    custom = "My team's custom prompt with {dictionary} slot."

    prompt = build_llm_system_prompt(["Foo"], custom_template=custom, usage_mode="daily")

    assert prompt == "My team's custom prompt with Foo slot."
    assert not has_vibe_coding_block(prompt)


def test_build_llm_prompt_custom_template_without_language_block_still_injects() -> None:
    """Custom prompt that lacks STRICT LANGUAGE MATCH — inject still works."""
    custom = "Custom editor. <CRITICAL_CONSTRAINTS>\n1. Be concise.\n</CRITICAL_CONSTRAINTS>"

    prompt = build_llm_system_prompt(["Y"], custom_template=custom, usage_mode="vibecoding")

    assert has_vibe_coding_block(prompt)
    assert "VIBE CODING PROTOCOL" in prompt


# ---------------------------------------------------------------------------
# inject / strip (still used for custom prompts)
# ---------------------------------------------------------------------------


def test_inject_vibe_coding_block_inserts_before_critical_constraints() -> None:
    result = inject_vibe_coding_block(DEFAULT_LLM_PROMPT_TEMPLATE)

    assert has_vibe_coding_block(result)
    assert "VIBE CODING PROTOCOL" in result
    vibe_pos = result.find("<VIBE_CODING_MODE_ACTIVE>")
    crit_pos = result.find("<CRITICAL_CONSTRAINTS>")
    assert vibe_pos < crit_pos, "Vibe block must appear BEFORE <CRITICAL_CONSTRAINTS>"


def test_inject_vibe_coding_block_prepends_for_custom_prompt() -> None:
    base = "Custom prompt without constraints."

    result = inject_vibe_coding_block(base)

    assert has_vibe_coding_block(result)
    assert result.endswith("Custom prompt without constraints.")


def test_inject_vibe_coding_block_is_idempotent() -> None:
    once = inject_vibe_coding_block(DEFAULT_LLM_PROMPT_TEMPLATE)

    twice = inject_vibe_coding_block(once)

    assert once == twice


def test_strip_vibe_coding_block_removes_block() -> None:
    with_block = inject_vibe_coding_block(DEFAULT_LLM_PROMPT_TEMPLATE)

    stripped = strip_vibe_coding_block(with_block)

    assert not has_vibe_coding_block(stripped)
    assert stripped.strip() == DEFAULT_LLM_PROMPT_TEMPLATE.strip()


def test_strip_vibe_coding_block_noop_when_absent() -> None:
    text = "No vibe block here."

    assert strip_vibe_coding_block(text) == text


# ---------------------------------------------------------------------------
# Migration: embedded vibe block in stored custom prompt
# ---------------------------------------------------------------------------


def test_build_llm_prompt_strips_embedded_vibe_block_from_stored_prompt() -> None:
    stored = inject_vibe_coding_block(DEFAULT_LLM_PROMPT_TEMPLATE)

    prompt = build_llm_system_prompt(["MLX"], custom_template=stored, usage_mode="daily")

    assert not has_vibe_coding_block(prompt)


def test_build_llm_prompt_strips_then_reinjects_for_vibecoding_custom() -> None:
    """If a stored custom prompt already has an embedded vibe block, strip it
    first, then apply the clean inject + neutralize pipeline."""
    stored = inject_vibe_coding_block(DEFAULT_LLM_PROMPT_TEMPLATE)

    prompt = build_llm_system_prompt(["MLX"], custom_template=stored, usage_mode="vibecoding")

    assert has_vibe_coding_block(prompt)
    assert "STRICT LANGUAGE MATCH" not in prompt


# ---------------------------------------------------------------------------
# Selection rewrite (unaffected by usage_mode)
# ---------------------------------------------------------------------------


def test_build_selection_rewrite_prompt_includes_constraints_and_dictionary() -> None:
    prompt = build_selection_rewrite_prompt(["周四", "周五"])

    assert "rewrite the selected text according to the user's instruction" in prompt
    assert "Output ONLY the rewritten selected text" in prompt
    assert "<DICTIONARY>" in prompt
    assert "周四" in prompt
    assert "周五" in prompt
