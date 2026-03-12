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
