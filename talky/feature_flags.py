"""Build-time and runtime feature gates for internal-only UI."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path


def _env_truthy(name: str) -> bool | None:
    raw = os.environ.get(name, "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return None


def _read_plist_debug_build() -> bool:
    if sys.platform != "darwin" or not getattr(sys, "frozen", False):
        return False
    try:
        exe = Path(sys.executable).resolve()
        plist_path = exe.parent.parent / "Info.plist"
        if not plist_path.is_file():
            return False
        import plistlib

        data = plistlib.loads(plist_path.read_bytes())
        return bool(data.get("TalkyDebugBuild", False))
    except Exception:
        return False


@lru_cache(maxsize=1)
def debug_ui_enabled() -> bool:
    """Whether internal dashboard controls (e.g. Save Debug Audio) are shown."""
    env = _env_truthy("TALKY_DEBUG_BUILD")
    if env is not None:
        return env
    if not getattr(sys, "frozen", False):
        return True
    return _read_plist_debug_build()
