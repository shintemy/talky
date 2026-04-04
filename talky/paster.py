from __future__ import annotations

import time

import pyperclip
from pynput.keyboard import Controller, Key


class ClipboardPaster:
    def __init__(self, paste_delay_ms: int = 120) -> None:
        self.paste_delay_ms = paste_delay_ms
        self._keyboard = Controller()

    def paste_text(self, text: str) -> None:
        pyperclip.copy(text)
        time.sleep(self.paste_delay_ms / 1000)
        with self._keyboard.pressed(Key.cmd):
            self._keyboard.press("v")
            self._keyboard.release("v")

    def capture_selected_text(self, copy_delay_ms: int = 80) -> str:
        try:
            previous_clipboard = pyperclip.paste()
        except Exception:
            previous_clipboard = ""

        with self._keyboard.pressed(Key.cmd):
            self._keyboard.press("c")
            self._keyboard.release("c")
        time.sleep(copy_delay_ms / 1000)

        try:
            captured = pyperclip.paste()
        except Exception:
            captured = ""

        # Restore clipboard so command mode does not pollute user's clipboard.
        try:
            pyperclip.copy(previous_clipboard)
        except Exception:
            pass

        return str(captured or "").strip()
