from __future__ import annotations

import re


def _contains_cjk(text: str) -> bool:
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            return True
    return False


def apply_phonetic_dictionary(text: str, dictionary_terms: list[str]) -> str:
    """
    Replace same-pronunciation variants with dictionary terms.

    This is a deterministic post-processing guard so the output aligns with
    user-maintained terminology even when ASR/LLM occasionally misses it.
    """
    if not text.strip():
        return text
    try:
        from pypinyin import Style, pinyin
    except Exception:
        # Keep app functional even if dependency is missing.
        return text

    def _to_pinyin(s: str) -> tuple[str, ...]:
        tokens = pinyin(s, style=Style.NORMAL, strict=False)
        return tuple(item[0] if item else "" for item in tokens)

    result = text
    terms = [term.strip() for term in dictionary_terms if term.strip()]
    terms.sort(key=len, reverse=True)

    for term in terms:
        if len(term) < 2 or not _contains_cjk(term):
            continue
        target = _to_pinyin(term)
        n = len(term)
        matches: list[int] = []
        for idx in range(0, len(result) - n + 1):
            segment = result[idx : idx + n]
            if segment == term:
                continue
            if not _contains_cjk(segment):
                continue
            if _to_pinyin(segment) == target:
                matches.append(idx)
        if not matches:
            continue
        for idx in reversed(matches):
            result = result[:idx] + term + result[idx + n :]
    return result


def normalize_person_pronouns(text: str, person_terms: list[str]) -> str:
    """
    When a person-marked dictionary term appears in a sentence, prefer pronoun
    "\u4ed6" over "\u5b83".
    """
    if not text.strip() or "\u5b83" not in text:
        return text
    terms = [term for term in person_terms if term]
    if not terms:
        return text

    parts = re.split(r"([\u3002\uff01\uff1f!?\n])", text)
    if not parts:
        return text

    rebuilt: list[str] = []
    idx = 0
    while idx < len(parts):
        body = parts[idx]
        sep = parts[idx + 1] if idx + 1 < len(parts) else ""
        if any(term in body for term in terms):
            body = body.replace("\u5b83", "\u4ed6")
        rebuilt.append(body + sep)
        idx += 2
    return "".join(rebuilt)
