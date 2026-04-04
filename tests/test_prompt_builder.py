from talky.prompting import (
    build_asr_initial_prompt,
    build_llm_system_prompt,
    build_selection_rewrite_prompt,
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


def test_build_selection_rewrite_prompt_includes_constraints_and_dictionary() -> None:
    prompt = build_selection_rewrite_prompt(["周四", "周五"])

    assert "rewrite the selected text according to the user's instruction" in prompt
    assert "Output ONLY the rewritten selected text" in prompt
    assert "<DICTIONARY>" in prompt
    assert "周四" in prompt
    assert "周五" in prompt
