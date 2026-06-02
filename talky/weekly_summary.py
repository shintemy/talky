from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path


def previous_iso_week_range(today: date) -> tuple[date, date]:
    """Return (Monday, Sunday) of the ISO week before today's week."""
    this_monday = today - timedelta(days=today.weekday())
    prev_monday = this_monday - timedelta(days=7)
    return prev_monday, prev_monday + timedelta(days=6)


def summary_filename(start: date, end: date) -> str:
    return f"summary-{start:%Y-%m-%d}_{end:%Y-%m-%d}.md"


def summary_path(summaries_dir: Path, start: date, end: date) -> Path:
    return summaries_dir / summary_filename(start, end)


def is_week_summarized(summaries_dir: Path, start: date, end: date) -> bool:
    path = summary_path(summaries_dir, start, end)
    try:
        return path.exists() and path.stat().st_size > 0
    except OSError:
        return False


def summary_language_for_locale(ui_locale: str) -> str:
    """Map UI locale to summary language code. Extend here for new locales."""
    return "zh" if ui_locale == "mixed" else "en"
