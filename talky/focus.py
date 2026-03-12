from __future__ import annotations

from dataclasses import dataclass


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


def has_focus_target(front_app: FrontAppInfo | None) -> bool:
    if front_app is None:
        return False
    if front_app.pid <= 0:
        return False
    name = front_app.name.strip().lower()
    # Desktop click often makes Finder frontmost without text caret.
    if name in {"finder", "dock", "loginwindow"}:
        return False
    return True
