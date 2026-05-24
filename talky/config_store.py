from __future__ import annotations

import json
from pathlib import Path

from talky.models import AppSettings, SESSION_START_USAGE_MODE, settings_for_disk


class AppConfigStore:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path

    def load(self) -> AppSettings:
        if not self.config_path.exists():
            return AppSettings()
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        settings = AppSettings.from_dict(data)
        raw_custom_prompt = str(data.get("custom_llm_prompt", "")).strip()
        if raw_custom_prompt and settings.custom_llm_prompt == "":
            # One-time migration: legacy built-in prompt snapshots should follow
            # the latest default prompt instead of permanently overriding it.
            data["custom_llm_prompt"] = ""
            self.config_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        raw_usage_mode = str(data.get("usage_mode", SESSION_START_USAGE_MODE)).strip().lower()
        if raw_usage_mode and raw_usage_mode != SESSION_START_USAGE_MODE:
            data["usage_mode"] = SESSION_START_USAGE_MODE
            self.config_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            settings.usage_mode = SESSION_START_USAGE_MODE
        return settings

    def save(self, settings: AppSettings) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(settings_for_disk(settings).to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
