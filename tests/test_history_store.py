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


def test_history_store_appends_final_output_and_raw_text(tmp_path: Path) -> None:
    history_dir = tmp_path / "history"
    store = HistoryStore(history_dir=history_dir)
    day = datetime(2026, 5, 10, 18, 30, 0)

    created_path = store.append(
        "整理后的最终文本",
        raw_text="Whisper 原始识别文本",
        now=day,
    )

    content = created_path.read_text(encoding="utf-8")
    assert "最终输出" in content
    assert "整理后的最终文本" in content
    assert "原文" in content
    assert "Whisper 原始识别文本" in content

    entries = store.read_entries("2026-05-10")
    assert entries == [
        (
            "18:30:00",
            "最终输出\n\n整理后的最终文本\n\n原文\n\nWhisper 原始识别文本",
        )
    ]


def test_history_store_appends_mode_and_language_metadata(tmp_path: Path) -> None:
    history_dir = tmp_path / "history"
    store = HistoryStore(history_dir=history_dir)
    day = datetime(2026, 5, 24, 16, 5, 0)

    store.append(
        "こんにちは",
        raw_text="你好",
        now=day,
        usage_mode="translation",
        asr_language="zh",
        translation_output_language="ja",
        debug_audio_path="/Users/test/.talky/debug-audio/sample.wav",
    )

    content = (history_dir / "2026-05-24.md").read_text(encoding="utf-8")
    assert "模式: Translation" in content
    assert "ASR 语言: zh" in content
    assert "目标语言: ja" in content
    assert "调试音频:" in content
    assert "sample.wav" in content
    assert "最终输出" in content
    assert "原文" in content

    entries = store.read_entries("2026-05-24")
    assert entries[0][0] == "16:05:00"
    assert "模式: Translation" in entries[0][1]
