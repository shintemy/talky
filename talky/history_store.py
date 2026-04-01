from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


class HistoryStore:
    def __init__(self, history_dir: Path) -> None:
        self.history_dir = history_dir

    def migrate_from(self, legacy_dirs: list[Path]) -> bool:
        """
        Copy legacy markdown history files into current history_dir once.
        Returns True if any file was migrated.
        """
        migrated = False
        self.history_dir.mkdir(parents=True, exist_ok=True)
        for legacy_dir in legacy_dirs:
            if legacy_dir.resolve() == self.history_dir.resolve():
                continue
            if not legacy_dir.exists() or not legacy_dir.is_dir():
                continue
            for src in legacy_dir.glob("*.md"):
                dst = self.history_dir / src.name
                if dst.exists():
                    continue
                try:
                    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                    migrated = True
                except Exception:
                    continue
        return migrated

    def append(self, text: str, now: datetime | None = None) -> Path:
        timestamp = now or datetime.now()
        self.history_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.history_dir / f"{timestamp:%Y-%m-%d}.md"
        entry = self._format_entry(text=text, timestamp=timestamp)
        with file_path.open("a", encoding="utf-8") as f:
            f.write(entry)
        return file_path

    def list_dates(self) -> list[str]:
        """Return date strings (YYYY-MM-DD) sorted newest first."""
        if not self.history_dir.exists():
            return []
        files = sorted(self.history_dir.glob("*.md"), reverse=True)
        return [f.stem for f in files]

    def read_entries(self, date_str: str) -> list[tuple[str, str]]:
        """Return (time_str, text) tuples for a given date, newest first."""
        file_path = self.history_dir / f"{date_str}.md"
        if not file_path.exists():
            return []
        content = file_path.read_text(encoding="utf-8")
        entries: list[tuple[str, str]] = []
        parts = re.split(
            r"^## (\d{2}:\d{2}:\d{2})\s*$", content, flags=re.MULTILINE
        )
        i = 1
        while i < len(parts) - 1:
            time_str = parts[i].strip()
            text = parts[i + 1].strip()
            if time_str:
                entries.append((time_str, text))
            i += 2
        entries.reverse()
        return entries

    def _format_entry(self, text: str, timestamp: datetime) -> str:
        safe_text = text.strip()
        return f"## {timestamp:%H:%M:%S}\n\n{safe_text}\n\n"
