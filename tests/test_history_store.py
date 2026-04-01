from __future__ import annotations

from talky.history_store import HistoryStore


def test_history_store_migrates_legacy_markdown_files(tmp_path) -> None:
    legacy = tmp_path / "legacy_history"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "2026-03-31.md").write_text("## 12:00:00\n\nhello\n\n", encoding="utf-8")
    target = tmp_path / "new_history"
    store = HistoryStore(target)

    changed = store.migrate_from([legacy])
    assert changed
    assert (target / "2026-03-31.md").exists()


def test_history_store_migration_keeps_existing_target_files(tmp_path) -> None:
    legacy = tmp_path / "legacy_history"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "2026-03-31.md").write_text("legacy", encoding="utf-8")
    target = tmp_path / "new_history"
    target.mkdir(parents=True, exist_ok=True)
    (target / "2026-03-31.md").write_text("new", encoding="utf-8")
    store = HistoryStore(target)

    changed = store.migrate_from([legacy])
    assert not changed
    assert (target / "2026-03-31.md").read_text(encoding="utf-8") == "new"
from datetime import datetime
from pathlib import Path

from talky.history_store import HistoryStore


def test_history_store_creates_daily_file_and_appends_entries(tmp_path: Path) -> None:
    history_dir = tmp_path / "history"
    store = HistoryStore(history_dir=history_dir)
    day = datetime(2026, 3, 13, 10, 11, 12)

    created_path = store.append("First line", now=day)
    store.append("Second line", now=day.replace(hour=11))

    assert created_path == history_dir / "2026-03-13.md"
    content = created_path.read_text(encoding="utf-8")
    assert "## 10:11:12" in content
    assert "First line" in content
    assert "## 11:11:12" in content
    assert "Second line" in content
