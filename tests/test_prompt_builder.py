from talky.prompting import build_asr_initial_prompt, build_llm_system_prompt


def test_build_asr_prompt_contains_dictionary_terms() -> None:
    dictionary = ["MLX", "Qwen", "Alice Chen"]

    prompt = build_asr_initial_prompt(dictionary)

    assert "MLX" in prompt
    assert "Qwen" in prompt
    assert "Alice Chen" in prompt


def test_build_llm_prompt_includes_required_rules() -> None:
    dictionary = ["TensorRT", "Alice Huang"]

    prompt = build_llm_system_prompt(dictionary)

    assert "Remove fillers and obvious ASR noise" in prompt
    assert "Rewrite only" in prompt
    assert "Keep the source language" in prompt
    assert "Do not translate" in prompt
    assert "Short question input -> output exactly one question sentence" in prompt
    assert "You are not a QA assistant" in prompt
    assert "Dictionary is correction-only" in prompt
    assert "clear section headers/lists" in prompt
    assert "grammar form consistent" in prompt
    assert "Output only the cleaned result" in prompt
    assert "TensorRT" in prompt
    assert "Alice Huang" in prompt
