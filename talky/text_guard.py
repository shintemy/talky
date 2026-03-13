from __future__ import annotations


def enforce_pronoun_consistency(source_text: str, output_text: str) -> str:
    """
    Keep pronouns aligned with source text to avoid unwanted rewrites.
    """
    source = source_text.strip()
    output = output_text.strip()
    if not source or not output:
        return output_text

    you = "\u4f60"
    formal_you = "\u60a8"
    me = "\u6211"
    my = "\u6211\u7684"
    your = "\u4f60\u7684"
    formal_your = "\u60a8\u7684"

    has_informal_you = you in source
    has_formal_you = formal_you in source
    has_source_you = has_informal_you or has_formal_you
    has_source_me = me in source

    result = output

    # If source is first-person-only, don't let model rewrite to second person.
    if has_source_me and not has_source_you:
        result = result.replace(formal_your, my).replace(your, my)
        result = result.replace(formal_you, me).replace(you, me)

    # If source is second-person-only, don't let model rewrite to first person.
    if has_source_you and not has_source_me:
        if has_formal_you and not has_informal_you:
            result = result.replace(my, formal_your)
            result = result.replace(me, formal_you)
        else:
            result = result.replace(formal_your, your).replace(my, your)
            result = result.replace(formal_you, you).replace(me, you)

    # If source uses informal second person, avoid formalizing to polite form.
    if has_informal_you and not has_formal_you:
        result = result.replace(formal_you, you)

    return result


def collapse_duplicate_output(text: str) -> str:
    """
    Collapse obvious duplicate output fragments, e.g.:
    - Two identical lines
    - Entire content repeated twice with only whitespace between copies
    """
    stripped = text.strip()
    if not stripped:
        return text

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(lines) >= 2 and all(line == lines[0] for line in lines):
        return lines[0]

    compact = "".join(stripped.split())
    if len(compact) % 2 == 0:
        half = len(compact) // 2
        if compact[:half] == compact[half:]:
            # Return first visible line/segment as canonical output.
            return lines[0] if lines else stripped[: len(stripped) // 2].strip()

    return stripped


def enforce_source_boundaries(source_text: str, output_text: str) -> str:
    """
    Prevent output from drifting into advice/extra-generation mode.
    If advisory markers appear only in output and it expands content notably,
    fallback to source text.
    """
    source = source_text.strip()
    output = output_text.strip()
    if not source or not output:
        return output_text

    advisory_markers = (
        "建议",
        "你可以",
        "可以考虑",
        "推荐",
        "应该",
        "方案",
        "步骤",
        "总结",
        "结论",
        "i suggest",
        "you should",
        "i recommend",
        "consider",
    )
    source_l = source.lower()
    output_l = output.lower()

    # Preserve question intent: source question should remain a question.
    source_is_question = _looks_like_question(source)
    output_is_question = _looks_like_question(output)
    if source_is_question and not output_is_question:
        return source

    introduced = any((m in output_l) and (m not in source_l) for m in advisory_markers)
    expanded = len(output) >= (len(source) + 8)
    starts_with_advice = output_l.startswith(("建议", "你可以", "可以考虑", "i suggest", "you should"))
    if introduced and (expanded or starts_with_advice):
        return source
    return output


def _looks_like_question(text: str) -> bool:
    value = text.strip()
    if not value:
        return False
    if value.endswith("?") or value.endswith("？"):
        return True
    lower = value.lower()
    prefixes = (
        "how ",
        "what ",
        "why ",
        "when ",
        "where ",
        "who ",
        "which ",
        "can ",
        "could ",
        "would ",
        "should ",
        "do ",
        "does ",
        "did ",
        "is ",
        "are ",
        "am ",
        "was ",
        "were ",
    )
    if lower.startswith(prefixes):
        return True
    # Chinese question heuristics:
    # - keep this strict to avoid false positives like declarative bullets
    #   that happen to contain "是否".
    if value.endswith(("吗", "么", "呢")):
        return True
    cn_prefixes = (
        "如何",
        "怎么",
        "怎样",
        "为什么",
        "为何",
        "是否",
        "能否",
        "可否",
        "是不是",
        "有无",
        "有没有",
        "哪些",
        "哪里",
        "哪儿",
        "多少",
        "几",
    )
    stripped = value.lstrip("“\"'（(")
    return stripped.startswith(cn_prefixes)
