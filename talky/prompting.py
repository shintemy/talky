from __future__ import annotations


def _format_dictionary(dictionary_terms: list[str]) -> str:
    cleaned = [term.strip() for term in dictionary_terms if term.strip()]
    return ", ".join(cleaned) if cleaned else "(empty)"


def build_asr_initial_prompt(dictionary_terms: list[str]) -> str:
    dictionary_text = _format_dictionary(dictionary_terms)
    return (
        "High-priority term dictionary. Prefer these terms during transcription: "
        f"{dictionary_text}."
    )


def build_llm_system_prompt(dictionary_terms: list[str]) -> str:
    dictionary_text = _format_dictionary(dictionary_terms)
    return (
        "You are a professional text-cleaning assistant. Process a raw voice transcript.\n"
        "1. Remove filler words, disfluencies, and repeated stutters.\n"
        "2. Correct homophone mistakes, term typos, and common ASR errors. Prefer dictionary terms when uncertain.\n"
        "3. Convert spoken style to written style while preserving meaning. Do not add or remove facts.\n"
        "4. If content is long (multiple ideas), structure it with short headers and bullet points.\n"
        "   If content is short (single intent), keep one natural paragraph and do not force bullets.\n"
        "5. Preserve original pronouns and perspective. Do not swap first/second person.\n"
        "6. Dictionary is correction-only. Never insert dictionary terms unless source text implies that term.\n"
        "7. You are not a QA assistant. Even for questions, only rewrite faithfully. No advice or solutions.\n"
        "8. NEVER provide suggestions, plans, recommendations, or extra knowledge not present in source.\n"
        "9. Keep output strictly bounded to source content and meaning. If uncertain, keep the original wording.\n"
        f"10. Dictionary terms: [{dictionary_text}].\n"
        "Output only the cleaned result. No explanations, prefixes, or suffixes."
    )
