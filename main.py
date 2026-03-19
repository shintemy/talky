from __future__ import annotations

import fcntl
import os
import signal
import sys
import threading
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from talky.permissions import (
    check_microphone_granted,
    is_accessibility_trusted,
    request_microphone_permission,
)

_SIGNAL_PUMP_TIMER = None
_PENDING_EXIT_SIGNAL: int | None = None
_EXIT_REQUESTED = False
_SINGLE_INSTANCE_LOCK_FD: int | None = None


def default_config_path() -> Path:
    return Path.home() / ".talky" / "settings.json"


def single_instance_lock_path() -> Path:
    return Path.home() / ".talky" / "talky.lock"


def show_settings_signal_path() -> Path:
    return Path.home() / ".talky" / "show_settings.signal"


def notify_running_instance_show_settings() -> None:
    signal_path = show_settings_signal_path()
    signal_path.parent.mkdir(parents=True, exist_ok=True)
    signal_path.write_text(str(os.getpid()), encoding="utf-8")


def try_acquire_single_instance_lock() -> bool:
    lock_path = single_instance_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return False
    except Exception:
        os.close(fd)
        return True

    try:
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode("utf-8"))
    except Exception:
        pass

    global _SINGLE_INSTANCE_LOCK_FD
    _SINGLE_INSTANCE_LOCK_FD = fd
    return True


def _force_exit_after_timeout(signum: int) -> None:
    app = QApplication.instance()
    if app is not None:
        os._exit(128 + signum)


def _request_graceful_exit(*, tray_app, controller, signum: int) -> None:
    global _EXIT_REQUESTED
    if _EXIT_REQUESTED:
        return
    _EXIT_REQUESTED = True

    fallback = threading.Timer(2.0, _force_exit_after_timeout, args=(signum,))
    fallback.daemon = True
    fallback.start()

    app = QApplication.instance()
    if app is not None:
        try:
            app.aboutToQuit.connect(fallback.cancel)
        except Exception:
            pass

    try:
        tray_app.quit_app()
    except Exception:
        try:
            controller.stop()
        except Exception:
            pass
        if app is not None:
            app.quit()


def _install_qt_signal_pump(*, tray_app, controller) -> None:
    qapp_instance = getattr(QApplication, "instance", None)
    if qapp_instance is None:
        return
    try:
        app = qapp_instance()
    except Exception:
        return
    if app is None:
        return

    try:
        from PyQt6.QtCore import QTimer
    except Exception:
        return

    timer = QTimer()
    timer.setInterval(200)
    def _poll_pending_exit() -> None:
        global _PENDING_EXIT_SIGNAL
        if _PENDING_EXIT_SIGNAL is None:
            return
        signum = _PENDING_EXIT_SIGNAL
        _PENDING_EXIT_SIGNAL = None
        _request_graceful_exit(
            tray_app=tray_app,
            controller=controller,
            signum=signum,
        )

    timer.timeout.connect(_poll_pending_exit)
    timer.start()

    try:
        app.aboutToQuit.connect(timer.stop)
    except Exception:
        pass

    global _SIGNAL_PUMP_TIMER
    _SIGNAL_PUMP_TIMER = timer

    try:
        app.setProperty("talky_signal_pump_timer", timer)
    except Exception:
        pass


def install_signal_handlers(*, tray_app, controller) -> None:
    def _handle_signal(signum, _frame) -> None:  # noqa: ANN001
        global _PENDING_EXIT_SIGNAL
        _PENDING_EXIT_SIGNAL = int(signum)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    _install_qt_signal_pump(tray_app=tray_app, controller=controller)


def _request_microphone_permission_after_start() -> None:
    mic_ok, _ = check_microphone_granted()
    if mic_ok:
        return
    request_microphone_permission()


def main() -> int:
    if not try_acquire_single_instance_lock():
        notify_running_instance_show_settings()
        print("Talky is already running. Skip duplicate launch.", file=sys.stderr)
        return 0

    from talky.config_store import AppConfigStore
    from talky.controller import AppController
    from talky.ui import SettingsWindow, TrayApp

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    try:
        from Foundation import (  # type: ignore[import-not-found]
            NSApplication,
            NSProcessInfo,
            NSUserDefaults,
        )

        NSApplication.sharedApplication().disableRelaunchOnLogin()
        NSProcessInfo.processInfo().disableAutomaticTermination_("Talky")
        NSUserDefaults.standardUserDefaults().setBool_forKey_(
            False, "NSQuitAlwaysKeepsWindows"
        )
    except Exception:
        pass

    try:
        from AppKit import NSApp, NSAppearance  # type: ignore[import-not-found]

        NSApp.setAppearance_(NSAppearance.appearanceNamed_("NSAppearanceNameAqua"))
    except Exception:
        pass

    config_store = AppConfigStore(default_config_path())
    controller = AppController(config_store=config_store)
    settings_window = SettingsWindow(controller=controller)
    tray_app = TrayApp(controller=controller, settings_window=settings_window)
    install_signal_handlers(tray_app=tray_app, controller=controller)

    if not is_accessibility_trusted(prompt=True):
        tray_app._show_error(  # noqa: SLF001 - startup prompt convenience
            "Accessibility permission missing. Auto-paste may fail. "
            "Grant permission in System Settings."
        )

    def _cleanup_on_quit() -> None:
        """Kill child processes so macOS doesn't think the app is still alive."""
        import multiprocessing
        import multiprocessing.resource_tracker
        import signal as _signal

        for child in multiprocessing.active_children():
            try:
                child.terminate()
                child.join(timeout=1)
                if child.is_alive():
                    child.kill()
            except Exception:
                pass
        try:
            tracker_pid = getattr(
                multiprocessing.resource_tracker._resource_tracker, "_pid", None
            )
            if tracker_pid:
                os.kill(tracker_pid, _signal.SIGTERM)
        except Exception:
            pass
        os._exit(0)

    app.aboutToQuit.connect(_cleanup_on_quit)

    controller.start()
    tray_app.show()
    try:
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(250, _request_microphone_permission_after_start)
    except Exception:
        pass
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
