from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import urllib.request


def _macos_version_tuple() -> tuple[int, int]:
    try:
        parts = platform.mac_ver()[0].split(".")
        major = int(parts[0]) if parts and parts[0].isdigit() else 0
        minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        return major, minor
    except Exception:
        return 0, 0


def input_monitoring_settings_url() -> str:
    """Deep link to Privacy & Security > Input Monitoring."""
    major, _minor = _macos_version_tuple()
    if major >= 13:
        return (
            "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension"
            "?Privacy_ListenEvent"
        )
    return "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"


def open_input_monitoring_settings() -> bool:
    """Open System Settings to Input Monitoring (best-effort)."""
    if sys.platform != "darwin":
        return False
    url = input_monitoring_settings_url()
    try:
        subprocess.run(["open", url], check=False)  # noqa: S603
        return True
    except Exception:
        pass
    try:
        from AppKit import NSWorkspace
        from Foundation import NSURL

        return bool(NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url)))
    except Exception:
        return False


def is_accessibility_trusted(prompt: bool = False) -> bool:
    try:
        from ApplicationServices import (
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )

        return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: prompt}))
    except Exception:
        return False


def check_input_monitoring_granted() -> bool:
    """Check macOS Input Monitoring (event tap) permission."""
    try:
        import Quartz

        preflight = getattr(Quartz, "CGPreflightListenEventAccess", None)
        if callable(preflight):
            return bool(preflight())
        # Older macOS / bindings may not expose this API; do not hard-block.
        return True
    except Exception:
        return False


def request_input_monitoring_permission() -> bool:
    """Request macOS Input Monitoring permission when missing."""
    if check_input_monitoring_granted():
        return True
    try:
        import Quartz

        request = getattr(Quartz, "CGRequestListenEventAccess", None)
        if callable(request):
            request()
    except Exception:
        pass
    return open_input_monitoring_settings()


def is_ollama_installed() -> bool:
    if shutil.which("ollama") is not None:
        return True
    # GUI apps often have a minimal PATH; Homebrew installs are common.
    if sys.platform == "darwin":
        for path in ("/opt/homebrew/bin/ollama", "/usr/local/bin/ollama"):
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return True
    return False


def check_microphone_granted() -> tuple[bool, str]:
    """
    Check microphone permission status without forcing prompt when possible.
    """
    try:
        import AVFoundation  # type: ignore[import-not-found]

        status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
            AVFoundation.AVMediaTypeAudio
        )
        authorized = int(status) == int(
            getattr(AVFoundation, "AVAuthorizationStatusAuthorized", 3)
        )
        if authorized:
            return True, ""
        return False, "Microphone permission not granted."
    except Exception:
        # Fallback path when AVFoundation bindings are unavailable.
        try:
            import sounddevice as sd

            stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32")
            stream.start()
            stream.stop()
            stream.close()
            return True, ""
        except Exception as exc:
            return False, f"Microphone permission not granted: {exc}"


def request_microphone_permission() -> tuple[bool, str]:
    """
    Trigger microphone permission prompt and return latest grant status.
    """
    try:
        import AVFoundation  # type: ignore[import-not-found]

        status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
            AVFoundation.AVMediaTypeAudio
        )
        not_determined = int(status) == int(
            getattr(AVFoundation, "AVAuthorizationStatusNotDetermined", 0)
        )
        authorized = int(status) == int(
            getattr(AVFoundation, "AVAuthorizationStatusAuthorized", 3)
        )
        if authorized:
            return True, ""
        if not not_determined:
            return False, "Microphone permission not granted."

        event = threading.Event()
        granted_holder = {"granted": False}

        def _handler(granted: bool) -> None:
            granted_holder["granted"] = bool(granted)
            event.set()

        AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            AVFoundation.AVMediaTypeAudio,
            _handler,
        )
        event.wait(timeout=5.0)
        if granted_holder["granted"]:
            return True, ""
        return False, "Microphone permission not granted."
    except Exception:
        # Fallback path: touching input stream may trigger system prompt.
        try:
            import sounddevice as sd

            stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32")
            stream.start()
            stream.stop()
            stream.close()
            return True, ""
        except Exception as exc:
            return False, f"Microphone permission not granted: {exc}"


def check_ollama_reachable() -> tuple[bool, str]:
    """Probe Ollama via HTTP only.

    The frozen app bundles the Python `ollama` package; using its Client here could
    behave differently from a real server and falsely report success. Match browser/tools.
    """
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    try:
        request = urllib.request.Request(  # noqa: S310
            url=f"{host}/api/tags",
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=8) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))
        if isinstance(data, dict) and "models" in data:
            return True, ""
        return False, "Ollama /api/tags response format is invalid."
    except Exception as exc:
        return False, f"Ollama service unavailable: {exc}"
