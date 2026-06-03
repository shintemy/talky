from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from talky.weekly_summary import summary_language_for_locale

SUMMARY_RE = re.compile(r"^summary-(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.md$")
DEFAULT_SUBFOLDER = "Talky"


def parse_summary_range(filename: str) -> tuple[date, date] | None:
    """Parse 'summary-START_END.md' into (start, end); None if it does not match.

    Expects a bare filename, not a full path.
    """
    match = SUMMARY_RE.match(filename)
    if not match:
        return None
    try:
        start = date.fromisoformat(match.group(1))
        end = date.fromisoformat(match.group(2))
    except ValueError:
        return None
    return start, end


def build_front_matter(start: date, end: date, *, lang: str) -> str:
    """Build a YAML front-matter block (trailing blank line included)."""
    if lang == "zh":
        title = f"周报 {start:%Y-%m-%d} ~ {end:%Y-%m-%d}"
        weekly_tag = "周报"
    else:
        title = f"Weekly Report {start:%Y-%m-%d} ~ {end:%Y-%m-%d}"
        weekly_tag = "weekly"
    return (
        "---\n"
        f'title: "{title}"\n'
        f'date_range: "{start:%Y-%m-%d}/{end:%Y-%m-%d}"\n'
        f"date: {end:%Y-%m-%d}\n"
        f"tags: [Talky, {weekly_tag}]\n"
        "source: Talky\n"
        "---\n\n"
    )


def prepend_front_matter(
    markdown: str, start: date, end: date, *, lang: str
) -> str:
    """Prepend front-matter to the summary body; skip if body already has one."""
    if markdown.lstrip().startswith("---"):
        return markdown
    return build_front_matter(start, end, lang=lang) + markdown
