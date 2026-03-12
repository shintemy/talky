from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from talky.config_store import AppConfigStore
from talky.controller import AppController
from talky.permissions import is_accessibility_trusted
from talky.ui import SettingsWindow, TrayApp


def default_config_path() -> Path:
    return Path.home() / ".talky" / "settings.json"


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config_store = AppConfigStore(default_config_path())
    controller = AppController(config_store=config_store)
    settings_window = SettingsWindow(controller=controller)
    tray_app = TrayApp(controller=controller, settings_window=settings_window)

    if not is_accessibility_trusted(prompt=True):
        tray_app._show_error(  # noqa: SLF001 - startup prompt convenience
            "Accessibility permission missing. Auto-paste may fail. "
            "Grant permission in System Settings."
        )

    controller.start()
    tray_app.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
