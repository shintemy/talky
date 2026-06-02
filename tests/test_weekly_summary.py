from __future__ import annotations

from datetime import date
from pathlib import Path

from talky.weekly_summary import (
    is_week_summarized,
    previous_iso_week_range,
    summary_filename,
    summary_language_for_locale,
    summary_path,
)


def test_previous_iso_week_range_midweek() -> None:
    # 2026-06-02 is a Tuesday; previous week is Mon 2026-05-25 .. Sun 2026-05-31
    start, end = previous_iso_week_range(date(2026, 6, 2))
    assert start == date(2026, 5, 25)
    assert end == date(2026, 5, 31)


def test_previous_iso_week_range_on_monday() -> None:
    start, end = previous_iso_week_range(date(2026, 6, 1))  # Monday
    assert start == date(2026, 5, 25)
    assert end == date(2026, 5, 31)


def test_previous_iso_week_range_crosses_year() -> None:
    start, end = previous_iso_week_range(date(2026, 1, 1))  # Thursday
    assert start == date(2025, 12, 22)
    assert end == date(2025, 12, 28)


def test_summary_filename_and_path() -> None:
    start, end = date(2026, 5, 25), date(2026, 5, 31)
    assert summary_filename(start, end) == "summary-2026-05-25_2026-05-31.md"
    assert summary_path(Path("/tmp/s"), start, end) == Path(
        "/tmp/s/summary-2026-05-25_2026-05-31.md"
    )


def test_is_week_summarized(tmp_path: Path) -> None:
    start, end = date(2026, 5, 25), date(2026, 5, 31)
    assert is_week_summarized(tmp_path, start, end) is False
    summary_path(tmp_path, start, end).write_text("x", encoding="utf-8")
    assert is_week_summarized(tmp_path, start, end) is True


def test_is_week_summarized_empty_file_is_not_done(tmp_path: Path) -> None:
    start, end = date(2026, 5, 25), date(2026, 5, 31)
    summary_path(tmp_path, start, end).write_text("", encoding="utf-8")
    assert is_week_summarized(tmp_path, start, end) is False


def test_summary_language_for_locale() -> None:
    assert summary_language_for_locale("mixed") == "zh"
    assert summary_language_for_locale("en") == "en"
    assert summary_language_for_locale("something-future") == "en"
