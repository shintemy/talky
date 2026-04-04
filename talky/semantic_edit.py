from __future__ import annotations

import re

_CJK_EDIT_PATTERNS = (
    r"改成",
    r"改为",
    r"改一下",
    r"替换成",
    r"替换为",
    r"换成",
    r"改到",
)

_EN_EDIT_PATTERNS = (
    r"\bchange\b.{0,40}\bto\b",
    r"\breplace\b.{0,40}\bwith\b",
)


def looks_like_edit_instruction(text: str) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    if len(value) > 80:
        return False

    lower = value.lower()
    for pattern in _EN_EDIT_PATTERNS:
        if re.search(pattern, lower):
            return True

    for pattern in _CJK_EDIT_PATTERNS:
        if re.search(pattern, value):
            return True
    return False
