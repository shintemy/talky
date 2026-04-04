from __future__ import annotations

import importlib
import sys
import types

import pytest


class _ImmediateThread:
    created: list["_ImmediateThread"] = []

    def __init__(self, target, daemon=None):  # noqa: ANN001, ANN204
        self._target = target
        self.daemon = daemon
        self._alive = False
        self.join_called = False
        _ImmediateThread.created.append(self)

    def start(self) -> None:
        self._alive = True
        self._target()

    def is_alive(self) -> bool:
        return self._alive

    def join(self, timeout=None) -> None:  # noqa: ANN001
        del timeout
        self.join_called = True
        self._alive = False


def _install_fake_quartz(monkeypatch: pytest.MonkeyPatch):
    state: dict[str, object] = {
        "callback": None,
        "tap": object(),
        "enable_calls": [],
    }

    def _tap_create(*args):  # noqa: ANN002, ANN003
        callback = args[4]
        state["callback"] = callback
        return state["tap"]

    def _tap_enable(tap, enabled):  # noqa: ANN001
        state["enable_calls"].append((tap, enabled))

    fake_quartz = types.SimpleNamespace(
        kCGEventFlagsChanged=42,
        kCGEventTapDisabledByTimeout=99,
        kCGEventTapDisabledByUserInput=100,
        kCGEventFlagMaskAlternate=0x1,
        kCGEventFlagMaskCommand=0x2,
        kCGEventFlagMaskControl=0x4,
        kCGEventFlagMaskShift=0x8,
        kCGEventFlagMaskSecondaryFn=0x10,
        kCGSessionEventTap=1,
        kCGHeadInsertEventTap=2,
        kCGEventTapOptionListenOnly=3,
        kCFRunLoopCommonModes=4,
        CGEventMaskBit=lambda _: 1,
        CGEventTapCreate=_tap_create,
        CFMachPortCreateRunLoopSource=lambda *_args: object(),
        CFRunLoopAddSource=lambda *_args: None,
        CGEventTapEnable=_tap_enable,
        CGEventGetFlags=lambda event: int(event),
        CGEventSourceFlagsState=lambda _state: 0,
        kCGEventSourceStateCombinedSessionState=7,
    )
    fake_cf = types.SimpleNamespace(
        CFRunLoopGetCurrent=lambda: object(),
        CFRunLoopRun=lambda: None,
        CFRunLoopStop=lambda _loop: None,
    )

    monkeypatch.setitem(sys.modules, "Quartz", fake_quartz)
    monkeypatch.setitem(sys.modules, "CoreFoundation", fake_cf)
    return state


def _reload_hotkey(monkeypatch: pytest.MonkeyPatch):
    _ImmediateThread.created = []
    state = _install_fake_quartz(monkeypatch)
    sys.modules.pop("talky.hotkey", None)
    mod = importlib.import_module("talky.hotkey")
    monkeypatch.setattr(mod.threading, "Thread", _ImmediateThread)
    return mod, state


def test_hold_to_talk_reenables_event_tap_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    hotkey_mod, quartz_state = _reload_hotkey(monkeypatch)
    presses: list[str] = []
    releases: list[str] = []

    listener = hotkey_mod.HoldToTalkHotkey(
        key_mode="fn",
        custom_keys=[],
        on_press=lambda: presses.append("p"),
        on_release=lambda: releases.append("r"),
    )
    listener.start()

    callback = quartz_state["callback"]
    assert callback is not None

    before = len(quartz_state["enable_calls"])
    callback(None, 99, 0, None)  # kCGEventTapDisabledByTimeout
    after = len(quartz_state["enable_calls"])
    assert after == before + 1
    assert quartz_state["enable_calls"][-1] == (quartz_state["tap"], True)
    assert presses == []
    assert releases == []


def test_global_shortcut_reenables_event_tap_after_disable(monkeypatch: pytest.MonkeyPatch) -> None:
    hotkey_mod, quartz_state = _reload_hotkey(monkeypatch)
    triggered: list[str] = []
    listener = hotkey_mod.GlobalShortcutListener(on_trigger=lambda: triggered.append("x"))
    listener.start()

    callback = quartz_state["callback"]
    assert callback is not None

    before = len(quartz_state["enable_calls"])
    callback(None, 100, 0, None)  # kCGEventTapDisabledByUserInput
    after = len(quartz_state["enable_calls"])
    assert after == before + 1
    assert quartz_state["enable_calls"][-1] == (quartz_state["tap"], True)
    assert triggered == []


def test_hold_to_talk_stop_joins_quartz_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    hotkey_mod, _ = _reload_hotkey(monkeypatch)
    listener = hotkey_mod.HoldToTalkHotkey(
        key_mode="fn",
        custom_keys=[],
        on_press=lambda: None,
        on_release=lambda: None,
    )
    listener.start()
    listener.stop()
    assert _ImmediateThread.created
    assert _ImmediateThread.created[-1].join_called


def test_hold_to_talk_fn_does_not_fire_when_initially_pressed(monkeypatch: pytest.MonkeyPatch) -> None:
    hotkey_mod, quartz_state = _reload_hotkey(monkeypatch)
    # Simulate system reporting Fn pressed at listener startup.
    quartz_mod = sys.modules["Quartz"]
    quartz_mod.CGEventSourceFlagsState = lambda _state: quartz_mod.kCGEventFlagMaskSecondaryFn

    presses: list[str] = []
    releases: list[str] = []
    listener = hotkey_mod.HoldToTalkHotkey(
        key_mode="fn",
        custom_keys=[],
        on_press=lambda: presses.append("p"),
        on_release=lambda: releases.append("r"),
    )
    listener.start()

    callback = quartz_state["callback"]
    assert callback is not None
    callback(None, quartz_mod.kCGEventFlagsChanged, quartz_mod.kCGEventFlagMaskSecondaryFn, None)
    assert presses == []
    # Release after startup should clear state.
    callback(None, quartz_mod.kCGEventFlagsChanged, 0, None)
    assert releases == ["r"]


def test_hold_to_talk_ensure_active_reenables_tap_when_healthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hotkey_mod, quartz_state = _reload_hotkey(monkeypatch)
    listener = hotkey_mod.HoldToTalkHotkey(
        key_mode="fn",
        custom_keys=[],
        on_press=lambda: None,
        on_release=lambda: None,
    )
    listener.start()

    before = len(quartz_state["enable_calls"])
    assert listener.is_healthy() is True
    assert listener.ensure_active() is True
    after = len(quartz_state["enable_calls"])
    assert after == before + 1
    assert quartz_state["enable_calls"][-1] == (quartz_state["tap"], True)


def test_hold_to_talk_ensure_active_returns_false_when_unhealthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hotkey_mod, _ = _reload_hotkey(monkeypatch)
    listener = hotkey_mod.HoldToTalkHotkey(
        key_mode="fn",
        custom_keys=[],
        on_press=lambda: None,
        on_release=lambda: None,
    )
    assert listener.is_healthy() is False
    assert listener.ensure_active() is False


def test_global_shortcut_does_not_phantom_trigger_when_initially_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hotkey_mod, quartz_state = _reload_hotkey(monkeypatch)
    quartz_mod = sys.modules["Quartz"]
    quartz_mod.CGEventSourceFlagsState = (
        lambda _state: quartz_mod.kCGEventFlagMaskAlternate
        | quartz_mod.kCGEventFlagMaskCommand
        | quartz_mod.kCGEventFlagMaskControl
    )
    triggered: list[str] = []
    listener = hotkey_mod.GlobalShortcutListener(on_trigger=lambda: triggered.append("x"))
    listener.start()

    callback = quartz_state["callback"]
    assert callback is not None
    # Same held state right after startup should not retrigger.
    callback(
        None,
        quartz_mod.kCGEventFlagsChanged,
        quartz_mod.kCGEventFlagMaskAlternate
        | quartz_mod.kCGEventFlagMaskCommand
        | quartz_mod.kCGEventFlagMaskControl,
        None,
    )
    assert triggered == []

    # Release then press combo should trigger once.
    callback(None, quartz_mod.kCGEventFlagsChanged, 0, None)
    callback(
        None,
        quartz_mod.kCGEventFlagsChanged,
        quartz_mod.kCGEventFlagMaskAlternate
        | quartz_mod.kCGEventFlagMaskCommand
        | quartz_mod.kCGEventFlagMaskControl,
        None,
    )
    assert triggered == ["x"]
