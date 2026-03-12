from __future__ import annotations

import threading
from collections.abc import Callable

from pynput import keyboard


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
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ) -> None:
        self.key_mode = key_mode
        self.on_press = on_press
        self.on_release = on_release
        self._pressed = False

        self._pynput_listener: keyboard.Listener | None = None
        self._quartz_thread: threading.Thread | None = None
        self._run_loop = None
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
        self._start_right_option_listener()

    def stop(self) -> None:
        if self._pynput_listener is not None:
            self._pynput_listener.stop()
            self._pynput_listener = None
        if self._run_loop is not None:
            try:
                import Quartz

                Quartz.CFRunLoopStop(self._run_loop)
            except Exception:
                pass
            self._run_loop = None

    def _start_right_option_listener(self) -> None:
        def _on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
            if key == keyboard.Key.alt_r and not self._pressed:
                self._pressed = True
                self.on_press()

        def _on_release(key: keyboard.Key | keyboard.KeyCode | None) -> None:
            if key == keyboard.Key.alt_r and self._pressed:
                self._pressed = False
                self.on_release()

        self._pynput_listener = keyboard.Listener(
            on_press=_on_press,
            on_release=_on_release,
        )
        self._pynput_listener.start()

    def _start_fn_quartz_listener(self) -> bool:
        try:
            import Quartz
        except Exception:
            return False

        fn_mask = getattr(Quartz, "kCGEventFlagMaskSecondaryFn", None)
        if fn_mask is None:
            return False

        def _run_event_tap() -> None:
            def _callback(proxy, event_type, event, refcon):
                del proxy, refcon
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
                Quartz.kCGEventTapOptionDefault,
                mask,
                _callback,
                None,
            )
            if tap is None:
                self._using_fallback = True
                self._start_right_option_listener()
                return

            source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            run_loop = Quartz.CFRunLoopGetCurrent()
            self._run_loop = run_loop
            Quartz.CFRunLoopAddSource(run_loop, source, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)
            Quartz.CFRunLoopRun()

        self._quartz_thread = threading.Thread(target=_run_event_tap, daemon=True)
        self._quartz_thread.start()
        return True


class GlobalShortcutListener:
    """
    Global shortcut listener for Command+Option+Control.
    """

    def __init__(self, on_trigger: Callable[[], None]) -> None:
        self.on_trigger = on_trigger
        self._listener: keyboard.Listener | None = None
        self._pressed_keys: set[object] = set()
        self._triggered_while_held = False

    def start(self) -> None:
        if self._listener is not None:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener is None:
            return
        self._listener.stop()
        self._listener = None
        self._pressed_keys.clear()
        self._triggered_while_held = False

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key is None:
            return
        self._pressed_keys.add(key)
        if self._is_match() and not self._triggered_while_held:
            self._triggered_while_held = True
            self.on_trigger()

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key is None:
            return
        self._pressed_keys.discard(key)
        if not self._is_match():
            self._triggered_while_held = False

    def _is_match(self) -> bool:
        option_pressed = any(
            k in self._pressed_keys
            for k in (keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt)
        )
        command_pressed = any(
            k in self._pressed_keys
            for k in (keyboard.Key.cmd_l, keyboard.Key.cmd_r, keyboard.Key.cmd)
        )
        control_pressed = any(
            k in self._pressed_keys
            for k in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.ctrl)
        )
        return option_pressed and command_pressed and control_pressed
