from __future__ import annotations

import threading
from collections.abc import Callable


def _safe_join_thread(worker: threading.Thread | None, timeout_s: float = 1.0) -> None:
    if worker is None:
        return
    try:
        is_alive = getattr(worker, "is_alive", None)
        if callable(is_alive) and not is_alive():
            return
        join = getattr(worker, "join", None)
        if callable(join):
            join(timeout_s)
    except Exception:
        pass


def label_for_hotkey_tokens(tokens: list[str]) -> str:
    labels = {
        "alt": "Option",
        "alt_l": "Left Option",
        "alt_r": "Right Option",
        "cmd": "Command",
        "cmd_l": "Left Command",
        "cmd_r": "Right Command",
        "ctrl": "Control",
        "ctrl_l": "Left Control",
        "ctrl_r": "Right Control",
        "shift": "Shift",
        "shift_l": "Left Shift",
        "shift_r": "Right Shift",
        "fn": "Fn",
        "space": "Space",
        "enter": "Enter",
        "esc": "Esc",
    }
    pretty: list[str] = []
    for token in tokens:
        if token.startswith("f") and token[1:].isdigit():
            pretty.append(token.upper())
        else:
            pretty.append(labels.get(token, token))
    return " + ".join(pretty)


class HoldToTalkHotkey:
    """
    Press-and-hold hotkey handler.

    On macOS, standalone Fn/Globe listening can be unreliable in high-level hooks.
    We first try Quartz flagsChanged with SecondaryFn mask; if unavailable, we
    gracefully fall back to Right Option (`alt_r`).
    """

    def __init__(
        self,
        key_mode: str,
        custom_keys: list[str],
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ) -> None:
        self.key_mode = key_mode
        self.custom_keys = [k.strip().lower() for k in custom_keys if k.strip()]
        self.on_press = on_press
        self.on_release = on_release
        self._pressed = False
        self._quartz_thread: threading.Thread | None = None
        self._run_loop = None
        self._tap = None
        self._using_fallback = False

    @property
    def using_fallback(self) -> bool:
        return self._using_fallback

    def start(self) -> None:
        if self.key_mode == "fn":
            started = self._start_fn_quartz_listener()
            if started:
                return
            self._using_fallback = True
            self._start_modifier_quartz_listener(required={"alt"})
            return

        if self.key_mode == "right_option":
            self._start_modifier_quartz_listener(required={"alt"})
            return
        if self.key_mode == "right_command":
            self._start_modifier_quartz_listener(required={"cmd"})
            return
        if self.key_mode == "command_option":
            self._start_modifier_quartz_listener(required={"cmd", "alt"})
            return
        if self.key_mode == "custom":
            supported = {"alt", "cmd", "ctrl", "shift", "fn"}
            required = {k for k in self.custom_keys if k in supported}
            if not required:
                required = {"alt"}
            self._start_modifier_quartz_listener(required=required)
            return

        self._start_modifier_quartz_listener(required={"alt"})

    def stop(self) -> None:
        thread = self._quartz_thread
        if self._run_loop is not None:
            try:
                from CoreFoundation import CFRunLoopStop

                CFRunLoopStop(self._run_loop)
            except Exception:
                pass
            self._run_loop = None
        if self._tap is not None:
            try:
                import Quartz

                invalidate = getattr(Quartz, "CFMachPortInvalidate", None)
                if callable(invalidate):
                    invalidate(self._tap)
            except Exception:
                pass
            self._tap = None
        _safe_join_thread(thread)
        self._quartz_thread = None
        self._pressed = False

    def is_healthy(self) -> bool:
        """Best-effort health check for quartz listener lifecycle."""
        thread = self._quartz_thread
        if thread is None:
            return False
        is_alive = getattr(thread, "is_alive", None)
        if not callable(is_alive) or not is_alive():
            return False
        if self._tap is None or self._run_loop is None:
            return False
        return True

    def ensure_active(self) -> bool:
        """Try to keep event tap enabled; return False when listener is unhealthy."""
        if not self.is_healthy():
            return False
        try:
            import Quartz

            Quartz.CGEventTapEnable(self._tap, True)
            return True
        except Exception:
            return False

    def _start_modifier_quartz_listener(self, required: set[str]) -> None:
        try:
            import Quartz
            from CoreFoundation import CFRunLoopGetCurrent, CFRunLoopRun
        except Exception:
            return

        alt_mask = getattr(Quartz, "kCGEventFlagMaskAlternate", 0)
        cmd_mask = getattr(Quartz, "kCGEventFlagMaskCommand", 0)
        ctrl_mask = getattr(Quartz, "kCGEventFlagMaskControl", 0)
        shift_mask = getattr(Quartz, "kCGEventFlagMaskShift", 0)
        fn_mask = getattr(Quartz, "kCGEventFlagMaskSecondaryFn", 0)
        tap_disabled_timeout = getattr(Quartz, "kCGEventTapDisabledByTimeout", None)
        tap_disabled_user_input = getattr(Quartz, "kCGEventTapDisabledByUserInput", None)

        # Initialize pressed state from current global flags. This prevents
        # phantom "pressed" transitions right after startup when modifier state
        # is already active or stale across sleep/wake.
        try:
            source_state = getattr(Quartz, "kCGEventSourceStateCombinedSessionState", 0)
            current_flags = Quartz.CGEventSourceFlagsState(source_state)
        except Exception:
            current_flags = 0
        current_mods: set[str] = set()
        if current_flags & alt_mask:
            current_mods.add("alt")
        if current_flags & cmd_mask:
            current_mods.add("cmd")
        if current_flags & ctrl_mask:
            current_mods.add("ctrl")
        if current_flags & shift_mask:
            current_mods.add("shift")
        if fn_mask and (current_flags & fn_mask):
            current_mods.add("fn")
        self._pressed = required.issubset(current_mods)

        def _run_event_tap() -> None:
            tap_ref = {"tap": None}

            def _callback(proxy, event_type, event, refcon):
                del proxy, refcon
                if event_type in {tap_disabled_timeout, tap_disabled_user_input}:
                    tap = tap_ref["tap"]
                    if tap is not None:
                        try:
                            Quartz.CGEventTapEnable(tap, True)
                        except Exception:
                            pass
                    return event
                if event_type != Quartz.kCGEventFlagsChanged:
                    return event

                flags = Quartz.CGEventGetFlags(event)
                current: set[str] = set()
                if flags & alt_mask:
                    current.add("alt")
                if flags & cmd_mask:
                    current.add("cmd")
                if flags & ctrl_mask:
                    current.add("ctrl")
                if flags & shift_mask:
                    current.add("shift")
                if fn_mask and (flags & fn_mask):
                    current.add("fn")

                is_match = required.issubset(current)
                if is_match and not self._pressed:
                    self._pressed = True
                    self.on_press()
                elif not is_match and self._pressed:
                    self._pressed = False
                    self.on_release()
                return event

            mask = Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly,
                mask,
                _callback,
                None,
            )
            tap_ref["tap"] = tap
            if tap is None:
                return
            self._tap = tap

            source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            run_loop = CFRunLoopGetCurrent()
            self._run_loop = run_loop
            Quartz.CFRunLoopAddSource(run_loop, source, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)
            CFRunLoopRun()

        self._quartz_thread = threading.Thread(target=_run_event_tap, daemon=True)
        self._quartz_thread.start()

    def _start_fn_quartz_listener(self) -> bool:
        try:
            import Quartz
            from CoreFoundation import CFRunLoopGetCurrent, CFRunLoopRun
        except Exception:
            return False

        fn_mask = getattr(Quartz, "kCGEventFlagMaskSecondaryFn", None)
        if fn_mask is None:
            return False
        tap_disabled_timeout = getattr(Quartz, "kCGEventTapDisabledByTimeout", None)
        tap_disabled_user_input = getattr(Quartz, "kCGEventTapDisabledByUserInput", None)

        # Seed pressed state from current flags to avoid startup false-positive.
        try:
            source_state = getattr(Quartz, "kCGEventSourceStateCombinedSessionState", 0)
            current_flags = Quartz.CGEventSourceFlagsState(source_state)
        except Exception:
            current_flags = 0
        self._pressed = bool(current_flags & fn_mask)

        def _run_event_tap() -> None:
            tap_ref = {"tap": None}

            def _callback(proxy, event_type, event, refcon):
                del proxy, refcon
                if event_type in {tap_disabled_timeout, tap_disabled_user_input}:
                    tap = tap_ref["tap"]
                    if tap is not None:
                        try:
                            Quartz.CGEventTapEnable(tap, True)
                        except Exception:
                            pass
                    return event
                if event_type != Quartz.kCGEventFlagsChanged:
                    return event
                flags = Quartz.CGEventGetFlags(event)
                is_pressed = bool(flags & fn_mask)
                if is_pressed and not self._pressed:
                    self._pressed = True
                    self.on_press()
                elif not is_pressed and self._pressed:
                    self._pressed = False
                    self.on_release()
                return event

            mask = Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly,
                mask,
                _callback,
                None,
            )
            tap_ref["tap"] = tap
            if tap is None:
                self._using_fallback = True
                self._start_modifier_quartz_listener(required={"alt"})
                return
            self._tap = tap

            source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            run_loop = CFRunLoopGetCurrent()
            self._run_loop = run_loop
            Quartz.CFRunLoopAddSource(run_loop, source, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)
            CFRunLoopRun()

        self._quartz_thread = threading.Thread(target=_run_event_tap, daemon=True)
        self._quartz_thread.start()
        return True


class GlobalShortcutListener:
    """
    Global shortcut listener for Command+Option+Control.
    Uses Quartz flagsChanged event tap to avoid pynput/ctypes instability
    seen on some macOS input-method environments.
    """

    def __init__(self, on_trigger: Callable[[], None]) -> None:
        self.on_trigger = on_trigger
        self._quartz_thread: threading.Thread | None = None
        self._run_loop = None
        self._tap = None
        self._triggered_while_held = False

    def start(self) -> None:
        if self._quartz_thread is not None:
            return
        try:
            import Quartz
            from CoreFoundation import CFRunLoopGetCurrent, CFRunLoopRun
        except Exception:
            return

        alt_mask = getattr(Quartz, "kCGEventFlagMaskAlternate", 0)
        cmd_mask = getattr(Quartz, "kCGEventFlagMaskCommand", 0)
        ctrl_mask = getattr(Quartz, "kCGEventFlagMaskControl", 0)
        tap_disabled_timeout = getattr(Quartz, "kCGEventTapDisabledByTimeout", None)
        tap_disabled_user_input = getattr(Quartz, "kCGEventTapDisabledByUserInput", None)

        # Seed held-state from current global flags to avoid startup phantom trigger.
        try:
            source_state = getattr(Quartz, "kCGEventSourceStateCombinedSessionState", 0)
            current_flags = Quartz.CGEventSourceFlagsState(source_state)
        except Exception:
            current_flags = 0
        self._triggered_while_held = bool(
            (current_flags & alt_mask) and (current_flags & cmd_mask) and (current_flags & ctrl_mask)
        )

        def _run_event_tap() -> None:
            tap_ref = {"tap": None}

            def _callback(proxy, event_type, event, refcon):
                del proxy, refcon
                if event_type in {tap_disabled_timeout, tap_disabled_user_input}:
                    tap = tap_ref["tap"]
                    if tap is not None:
                        try:
                            Quartz.CGEventTapEnable(tap, True)
                        except Exception:
                            pass
                    return event
                if event_type != Quartz.kCGEventFlagsChanged:
                    return event
                flags = Quartz.CGEventGetFlags(event)
                match = bool((flags & alt_mask) and (flags & cmd_mask) and (flags & ctrl_mask))
                if match and not self._triggered_while_held:
                    self._triggered_while_held = True
                    self.on_trigger()
                elif not match:
                    self._triggered_while_held = False
                return event

            mask = Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly,
                mask,
                _callback,
                None,
            )
            tap_ref["tap"] = tap
            if tap is None:
                return
            self._tap = tap
            source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            run_loop = CFRunLoopGetCurrent()
            self._run_loop = run_loop
            Quartz.CFRunLoopAddSource(run_loop, source, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)
            CFRunLoopRun()

        self._quartz_thread = threading.Thread(target=_run_event_tap, daemon=True)
        self._quartz_thread.start()

    def stop(self) -> None:
        thread = self._quartz_thread
        if self._run_loop is not None:
            try:
                from CoreFoundation import CFRunLoopStop

                CFRunLoopStop(self._run_loop)
            except Exception:
                pass
            self._run_loop = None
        if self._tap is not None:
            try:
                import Quartz

                invalidate = getattr(Quartz, "CFMachPortInvalidate", None)
                if callable(invalidate):
                    invalidate(self._tap)
            except Exception:
                pass
            self._tap = None
        _safe_join_thread(thread)
        self._quartz_thread = None
        self._triggered_while_held = False
