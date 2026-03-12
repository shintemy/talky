from __future__ import annotations

from datetime import datetime
from pathlib import Path


class HistoryStore:
    def __init__(self, history_dir: Path) -> None:
        self.history_dir = history_dir

    def append(self, text: str, now: datetime | None = None) -> Path:
        timestamp = now or datetime.now()
        self.history_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.history_dir / f"{timestamp:%Y-%m-%d}.md"
        entry = self._format_entry(text=text, timestamp=timestamp)
        with file_path.open("a", encoding="utf-8") as f:
            f.write(entry)
        return file_path

    def _format_entry(self, text: str, timestamp: datetime) -> str:
        safe_text = text.strip()
        return f"## {timestamp:%H:%M:%S}\n\n{safe_text}\n\n"
