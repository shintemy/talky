from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from talky.history_store import StructuredHistoryEntry


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


_WEEKDAYS = {
    "zh": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}
_LABELS = {
    "zh": {"title": "周报", "overview": "概览", "byday": "按天"},
    "en": {"title": "Weekly Report", "overview": "Overview", "byday": "By Day"},
}


@dataclass(frozen=True)
class DayOutputs:
    day: date
    entries: list[StructuredHistoryEntry]


def collect_week_outputs(
    read_structured: Callable[[str], list[StructuredHistoryEntry]],
    start: date,
    end: date,
) -> list[DayOutputs]:
    days: list[DayOutputs] = []
    current = start
    while current <= end:
        entries = [
            e
            for e in read_structured(current.strftime("%Y-%m-%d"))
            if e.final_text.strip()
        ]
        if entries:
            entries.sort(key=lambda e: e.time_str)
            days.append(DayOutputs(day=current, entries=entries))
        current += timedelta(days=1)
    return days


def _weekday_label(day: date, lang: str) -> str:
    return _WEEKDAYS.get(lang, _WEEKDAYS["en"])[day.weekday()]


def build_day_system_prompt(lang: str) -> str:
    if lang == "zh":
        return (
            "你是简洁的中文助理。下面是用户某一天的语音转写最终输出（按时间排列）。"
            "请整理成 3-6 条要点小结，只基于给定内容，不要新增建议或评论，不要编造。"
            "直接输出中文要点，每条一行。"
        )
    return (
        "You are a concise assistant. Below are the user's final dictation outputs "
        "for a single day (in time order). Summarize them into 3-6 bullet points. "
        "Use only the given content; do not add advice or fabricate. Output English "
        "bullets, one per line."
    )


def build_day_user_content(day: DayOutputs, lang: str) -> str:
    header = f"{day.day:%Y-%m-%d} {_weekday_label(day.day, lang)}"
    lines = [header]
    for entry in day.entries:
        mode = f" [{entry.usage_mode}]" if entry.usage_mode else ""
        lines.append(f"- {entry.time_str}{mode} {entry.final_text}")
    return "\n".join(lines)


def build_reduce_system_prompt(lang: str) -> str:
    if lang == "zh":
        return (
            "你是简洁的中文助理。下面是用户上一周每天的内容小结。"
            "请综合成一段本周概览（3-6 句），概括主要主题、进展与重点。"
            "只基于给定内容，不要编造。直接输出中文。"
        )
    return (
        "You are a concise assistant. Below are per-day digests of the user's last "
        "week. Write a single weekly overview (3-6 sentences) covering the main "
        "themes, progress, and highlights. Use only the given content; do not "
        "fabricate. Output English."
    )


def build_reduce_user_content(
    day_summaries: list[tuple[date, str]], start: date, end: date, lang: str
) -> str:
    blocks = [f"{start:%Y-%m-%d} ~ {end:%Y-%m-%d}"]
    for day, summary in day_summaries:
        blocks.append(f"{day:%Y-%m-%d} {_weekday_label(day, lang)}:\n{summary}")
    return "\n\n".join(blocks)


def render_summary_markdown(
    *,
    start: date,
    end: date,
    overview: str,
    day_summaries: list[tuple[date, str]],
    total_entries: int,
    lang: str,
    now_text: str,
    model_name: str,
) -> str:
    labels = _LABELS.get(lang, _LABELS["en"])
    days_count = len(day_summaries)
    if lang == "zh":
        meta = (
            f"> 生成于 {now_text} · 模型 {model_name} · "
            f"共 {total_entries} 条输出 / 覆盖 {days_count} 天"
        )
    else:
        meta = (
            f"> Generated {now_text} · model {model_name} · "
            f"{total_entries} outputs / {days_count} days"
        )
    parts = [
        f"# {labels['title']} {start:%Y-%m-%d} ~ {end:%Y-%m-%d}",
        "",
        meta,
        "",
        f"## {labels['overview']}",
        "",
        overview.strip(),
        "",
        f"## {labels['byday']}",
    ]
    for day, summary in day_summaries:
        parts.append("")
        parts.append(f"### {day:%m-%d} {_weekday_label(day, lang)}")
        parts.append("")
        parts.append(summary.strip())
    return "\n".join(parts) + "\n"
