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


from datetime import date as _date

from talky.history_store import StructuredHistoryEntry
from talky.weekly_summary import (
    DayOutputs,
    collect_week_outputs,
    render_summary_markdown,
)


def _entry(t: str, mode: str, text: str) -> StructuredHistoryEntry:
    return StructuredHistoryEntry(
        time_str=t, usage_mode=mode, final_text=text, matched_persons=(), matched_terms=()
    )


def test_collect_week_outputs_skips_empty_days_and_sorts(tmp_path) -> None:
    data = {
        "2026-05-25": [_entry("11:00:00", "daily", "b"), _entry("09:00:00", "daily", "a")],
        "2026-05-27": [],
        "2026-05-28": [_entry("10:00:00", "vibecoding", "c")],
    }

    def fake_read(date_str: str):
        return list(data.get(date_str, []))

    days = collect_week_outputs(fake_read, _date(2026, 5, 25), _date(2026, 5, 31))

    assert [d.day for d in days] == [_date(2026, 5, 25), _date(2026, 5, 28)]
    # sorted ascending by time_str within a day
    assert [e.final_text for e in days[0].entries] == ["a", "b"]


def test_render_summary_markdown_zh() -> None:
    days = [
        ("2026-05-25", _date(2026, 5, 25), "周一小结"),
        ("2026-05-28", _date(2026, 5, 28), "周四小结"),
    ]
    md = render_summary_markdown(
        start=_date(2026, 5, 25),
        end=_date(2026, 5, 31),
        overview="本周概览内容",
        day_summaries=[(d[1], d[2]) for d in days],
        total_entries=5,
        lang="zh",
        now_text="2026-06-01 09:00",
        model_name="qwen3.5:9b",
    )
    assert md.startswith("# 周报 2026-05-25 ~ 2026-05-31")
    assert "## 概览" in md
    assert "本周概览内容" in md
    assert "## 按天" in md
    assert "### 05-25 周一" in md
    assert "周一小结" in md
    assert "### 05-28 周四" in md
    assert "共 5 条输出 / 覆盖 2 天" in md


def test_render_summary_markdown_en() -> None:
    md = render_summary_markdown(
        start=_date(2026, 5, 25),
        end=_date(2026, 5, 31),
        overview="overview body",
        day_summaries=[(_date(2026, 5, 25), "monday digest")],
        total_entries=1,
        lang="en",
        now_text="2026-06-01 09:00",
        model_name="qwen3.5:9b",
    )
    assert md.startswith("# Weekly Report 2026-05-25 ~ 2026-05-31")
    assert "## Overview" in md
    assert "## By Day" in md
    assert "### 05-25 Mon" in md
    assert "1 outputs / 1 days" in md


from talky.weekly_summary import run_weekly_summary


def _ok_run(**overrides):
    """Build default args for run_weekly_summary; override as needed."""
    data = {
        "2026-05-25": [_entry("09:00:00", "daily", "a")],
        "2026-05-26": [_entry("09:00:00", "vibecoding", "b")],
    }
    args = dict(
        today=_date(2026, 6, 2),
        summaries_dir=overrides.pop("summaries_dir"),
        read_structured=lambda d: list(data.get(d, [])),
        summarize=lambda content, system_prompt: f"SUM[{content[:6]}]",
        is_ready=lambda: True,
        should_abort=lambda: False,
        ui_locale="mixed",
        model_name="qwen3.5:9b",
        now_text="2026-06-01 09:00",
    )
    args.update(overrides)
    return args


def test_run_weekly_summary_writes_file(tmp_path) -> None:
    path = run_weekly_summary(**_ok_run(summaries_dir=tmp_path))
    assert path is not None
    assert path == tmp_path / "summary-2026-05-25_2026-05-31.md"
    content = path.read_text(encoding="utf-8")
    assert "# 周报 2026-05-25 ~ 2026-05-31" in content
    assert "共 2 条输出 / 覆盖 2 天" in content
    # no leftover temp file
    assert list(tmp_path.glob("*.tmp")) == []


def test_run_weekly_summary_skips_when_already_done(tmp_path) -> None:
    (tmp_path / "summary-2026-05-25_2026-05-31.md").write_text("x", encoding="utf-8")
    called = {"n": 0}

    def counting_summarize(content, system_prompt):
        called["n"] += 1
        return "x"

    path = run_weekly_summary(
        **_ok_run(summaries_dir=tmp_path, summarize=counting_summarize)
    )
    assert path is None
    assert called["n"] == 0


def test_run_weekly_summary_skips_when_not_ready(tmp_path) -> None:
    path = run_weekly_summary(**_ok_run(summaries_dir=tmp_path, is_ready=lambda: False))
    assert path is None
    assert list(tmp_path.glob("*.md")) == []


def test_run_weekly_summary_skips_empty_week(tmp_path) -> None:
    path = run_weekly_summary(
        **_ok_run(summaries_dir=tmp_path, read_structured=lambda d: [])
    )
    assert path is None
    assert list(tmp_path.glob("*.md")) == []


def test_run_weekly_summary_aborts_without_writing(tmp_path) -> None:
    path = run_weekly_summary(
        **_ok_run(summaries_dir=tmp_path, should_abort=lambda: True)
    )
    assert path is None
    assert list(tmp_path.glob("*.md")) == []


def test_run_weekly_summary_does_not_write_on_summarize_error(tmp_path) -> None:
    def boom(content, system_prompt):
        raise RuntimeError("llm down")

    try:
        run_weekly_summary(**_ok_run(summaries_dir=tmp_path, summarize=boom))
    except RuntimeError:
        pass
    assert list(tmp_path.glob("*.md")) == []
    assert list(tmp_path.glob("*.tmp")) == []
