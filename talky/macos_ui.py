"""macOS-only helpers so Qt dialogs appear above other apps when launched from Finder/Dock."""

from __future__ import annotations

import sys
from typing import Any, Callable

_DOCK_REOPEN_DELEGATE = None


def activate_foreground_app() -> None:
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApplication

        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    except Exception:
        return


def prepare_qt_modal_for_macos(widget: Any) -> None:
    """Raise app and keep a dialog/message box above other windows (best-effort)."""
    activate_foreground_app()
    try:
        from PyQt6.QtCore import Qt

        widget.setWindowFlags(widget.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    except Exception:
        pass


def install_dock_reopen_handler(on_reopen: Callable[[], None]) -> None:
    """Invoke callback when user clicks the running app's Dock icon."""
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApplication
        from Foundation import NSObject
    except Exception:
        return

    app = NSApplication.sharedApplication()
    original_delegate = app.delegate()

    class _DockReopenDelegate(NSObject):
        def initWithOriginal_onReopen_(self, original, callback):
            self = _DockReopenDelegate.alloc().init()
            if self is None:
                return None
            self._original_delegate = original
            self._on_reopen = callback
            return self

        def applicationShouldHandleReopen_hasVisibleWindows_(self, sender, flag):  # noqa: N802, ANN001
            try:
                self._on_reopen()
            except Exception:
                pass
            original = getattr(self, "_original_delegate", None)
            if (
                original is not None
                and hasattr(original, "applicationShouldHandleReopen_hasVisibleWindows_")
            ):
                try:
                    return bool(
                        original.applicationShouldHandleReopen_hasVisibleWindows_(
                            sender, flag
                        )
                    )
                except Exception:
                    pass
            return True

        def respondsToSelector_(self, selector):  # noqa: N802, ANN001
            try:
                if super().respondsToSelector_(selector):
                    return True
            except Exception:
                pass
            original = getattr(self, "_original_delegate", None)
            return bool(
                original is not None
                and hasattr(original, "respondsToSelector_")
                and original.respondsToSelector_(selector)
            )

        def forwardingTargetForSelector_(self, selector):  # noqa: N802, ANN001
            original = getattr(self, "_original_delegate", None)
            if (
                original is not None
                and hasattr(original, "respondsToSelector_")
                and original.respondsToSelector_(selector)
            ):
                return original
            return None

    delegate = _DockReopenDelegate.alloc().initWithOriginal_onReopen_(
        original_delegate, on_reopen
    )
    if delegate is None:
        return

    global _DOCK_REOPEN_DELEGATE
    _DOCK_REOPEN_DELEGATE = delegate
    app.setDelegate_(delegate)
