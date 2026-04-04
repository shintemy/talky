from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class FrontAppInfo:
    name: str
    pid: int


def get_frontmost_app() -> FrontAppInfo | None:
    try:
        from AppKit import NSWorkspace

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return None
        name = str(app.localizedName() or "")
        pid = int(app.processIdentifier())
        return FrontAppInfo(name=name, pid=pid)
    except Exception:
        return None


def activate_app_by_pid(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        from AppKit import NSRunningApplication

        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        if app is None:
            return False
        # 1 << 1 = NSApplicationActivateIgnoringOtherApps
        return bool(app.activateWithOptions_(1 << 1))
    except Exception:
        return False


def has_focus_target(front_app: FrontAppInfo | None) -> bool:
    if front_app is None:
        return False
    if front_app.pid <= 0:
        return False
    name = front_app.name.strip().lower()
    if not name:
        return False
    if name in {"finder", "dock", "loginwindow"}:
        return False
    # Name-exclusion passed → treat as valid target by default.
    # AX editable check is an optional enhancement only; it must never
    # downgrade the decision to False because the API is unreliable
    # (only works on the frontmost app and many apps lack standard roles).
    return True


def _app_has_editable_text_focus(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        from ApplicationServices import (
            AXUIElementCopyAttributeValue,
            AXUIElementCreateApplication,
            kAXEditableAttribute,
            kAXEnabledAttribute,
            kAXFocusedUIElementAttribute,
            kAXRoleAttribute,
        )
    except Exception:
        return False

    try:
        app_el = AXUIElementCreateApplication(pid)
        focused_el = _ax_get_attr(
            AXUIElementCopyAttributeValue,
            app_el,
            kAXFocusedUIElementAttribute,
        )
        if focused_el is None:
            return False

        editable = _ax_get_attr(
            AXUIElementCopyAttributeValue,
            focused_el,
            kAXEditableAttribute,
        )
        if isinstance(editable, bool) and editable:
            enabled = _ax_get_attr(
                AXUIElementCopyAttributeValue,
                focused_el,
                kAXEnabledAttribute,
            )
            return enabled is not False

        role = str(
            _ax_get_attr(
                AXUIElementCopyAttributeValue,
                focused_el,
                kAXRoleAttribute,
            )
            or ""
        ).lower()
        return role in {
            "axtextfield",
            "axtextarea",
            "axsearchfield",
            "axcombobox",
        }
    except Exception:
        return False


def _ax_get_attr(copy_func, element: Any, attr: str) -> Any:
    """
    Safely normalize AXUIElementCopyAttributeValue return shapes across bindings.

    pyobjc always returns ``(AXError, value)``; AXError == 0 means success.
    """
    try:
        raw = copy_func(element, attr)
    except TypeError:
        raw = copy_func(element, attr, None)

    if isinstance(raw, tuple):
        if len(raw) == 2:
            err, value = raw
            if err == 0:
                return value
            return None
        if raw:
            return raw[-1]
        return None
    return raw
