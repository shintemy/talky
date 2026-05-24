from __future__ import annotations

import importlib
import sys
import types

import pytest


def test_debug_ui_enabled_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import talky.feature_flags as feature_flags

    feature_flags.debug_ui_enabled.cache_clear()
    monkeypatch.setattr(feature_flags, "_read_plist_debug_build", lambda: False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    monkeypatch.setenv("TALKY_DEBUG_BUILD", "1")
    assert feature_flags.debug_ui_enabled() is True

    feature_flags.debug_ui_enabled.cache_clear()
    monkeypatch.setenv("TALKY_DEBUG_BUILD", "0")
    assert feature_flags.debug_ui_enabled() is False


def test_debug_ui_enabled_true_when_running_from_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import talky.feature_flags as feature_flags

    feature_flags.debug_ui_enabled.cache_clear()
    monkeypatch.delenv("TALKY_DEBUG_BUILD", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    assert feature_flags.debug_ui_enabled() is True


def test_debug_ui_enabled_reads_plist_in_frozen_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import talky.feature_flags as feature_flags

    feature_flags.debug_ui_enabled.cache_clear()
    monkeypatch.delenv("TALKY_DEBUG_BUILD", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(feature_flags, "_read_plist_debug_build", lambda: False)

    assert feature_flags.debug_ui_enabled() is False

    feature_flags.debug_ui_enabled.cache_clear()
    monkeypatch.setattr(feature_flags, "_read_plist_debug_build", lambda: True)
    assert feature_flags.debug_ui_enabled() is True
