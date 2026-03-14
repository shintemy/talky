from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from talky.ui import _tr


def test_mixed_locale_uses_chinese_only_for_known_keys() -> None:
    assert _tr("mixed", "Save", "save") == "保存"
    assert _tr("mixed", "UI Language", "ui_language") == "UI 语言"


def test_mixed_locale_falls_back_to_english_when_key_missing() -> None:
    assert _tr("mixed", "Fallback Text", "missing_key") == "Fallback Text"
    assert _tr("mixed", "Fallback Text", None) == "Fallback Text"
