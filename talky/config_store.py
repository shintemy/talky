from __future__ import annotations

import json
from pathlib import Path

from talky.models import AppSettings


class AppConfigStore:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path

    def load(self) -> AppSettings:
        if not self.config_path.exists():
            return AppSettings()
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        return AppSettings.from_dict(data)

    def save(self, settings: AppSettings) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(settings.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
