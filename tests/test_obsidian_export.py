from datetime import date

from talky.obsidian_export import (
    build_front_matter,
    parse_summary_range,
    prepend_front_matter,
)


def test_parse_summary_range_valid():
    assert parse_summary_range("summary-2026-05-25_2026-05-31.md") == (
        date(2026, 5, 25),
        date(2026, 5, 31),
    )


def test_parse_summary_range_rejects_non_matching():
    assert parse_summary_range("notes.md") is None
    assert parse_summary_range("summary-2026-05-25.md") is None
    assert parse_summary_range("summary-2026-05-25_2026-05-31.txt") is None


def test_parse_summary_range_rejects_impossible_date():
    assert parse_summary_range("summary-2026-13-99_2026-05-31.md") is None


def test_build_front_matter_zh():
    fm = build_front_matter(date(2026, 5, 25), date(2026, 5, 31), lang="zh")
    assert fm.startswith("---\n")
    assert 'title: "周报 2026-05-25 ~ 2026-05-31"' in fm
    assert 'date_range: "2026-05-25/2026-05-31"' in fm
    assert "date: 2026-05-31" in fm
    assert "tags: [Talky, 周报]" in fm
    assert fm.endswith("---\n\n")


def test_build_front_matter_en():
    fm = build_front_matter(date(2026, 5, 25), date(2026, 5, 31), lang="en")
    assert 'title: "Weekly Report 2026-05-25 ~ 2026-05-31"' in fm
    assert "tags: [Talky, weekly]" in fm


def test_prepend_front_matter_adds_block():
    body = "# 周报 2026-05-25 ~ 2026-05-31\n\nhello\n"
    out = prepend_front_matter(body, date(2026, 5, 25), date(2026, 5, 31), lang="zh")
    assert out.startswith("---\n")
    assert out.endswith(body)


def test_prepend_front_matter_skips_when_already_present():
    body = "---\ntitle: x\n---\n\n# already\n"
    out = prepend_front_matter(body, date(2026, 5, 25), date(2026, 5, 31), lang="zh")
    assert out == body
