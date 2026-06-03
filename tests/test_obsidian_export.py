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
    assert fm.startswith("---\n")
    assert 'title: "Weekly Report 2026-05-25 ~ 2026-05-31"' in fm
    assert 'date_range: "2026-05-25/2026-05-31"' in fm
    assert "date: 2026-05-31" in fm
    assert "tags: [Talky, weekly]" in fm
    assert fm.endswith("---\n\n")


def test_prepend_front_matter_adds_block():
    body = "# 周报 2026-05-25 ~ 2026-05-31\n\nhello\n"
    out = prepend_front_matter(body, date(2026, 5, 25), date(2026, 5, 31), lang="zh")
    assert out.startswith("---\n")
    assert out.endswith(body)


def test_prepend_front_matter_skips_when_already_present():
    body = "---\ntitle: x\n---\n\n# already\n"
    out = prepend_front_matter(body, date(2026, 5, 25), date(2026, 5, 31), lang="zh")
    assert out == body


from pathlib import Path
from types import SimpleNamespace

from talky.obsidian_export import (
    ExportResult,
    export_all_summaries,
    run_export,
)


def _write_summary(summaries_dir: Path, name: str, body: str = "# body\n") -> None:
    summaries_dir.mkdir(parents=True, exist_ok=True)
    (summaries_dir / name).write_text(body, encoding="utf-8")


def test_export_all_writes_fresh_with_front_matter(tmp_path):
    summaries = tmp_path / "summaries"
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_summary(summaries, "summary-2026-05-25_2026-05-31.md", "# 周报\n\nhi\n")

    result = export_all_summaries(
        summaries_dir=summaries, vault_path=vault, lang="zh"
    )

    assert result.exported == ("summary-2026-05-25_2026-05-31.md",)
    assert result.skipped == ()
    target = vault / "Talky" / "summary-2026-05-25_2026-05-31.md"
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "tags: [Talky, 周报]" in text
    assert text.endswith("# 周报\n\nhi\n")


def test_export_all_skips_existing_without_overwrite(tmp_path):
    summaries = tmp_path / "summaries"
    vault = tmp_path / "vault"
    target_dir = vault / "Talky"
    target_dir.mkdir(parents=True)
    name = "summary-2026-05-25_2026-05-31.md"
    _write_summary(summaries, name, "# new\n")
    (target_dir / name).write_text("KEEP MY EDIT\n", encoding="utf-8")

    result = export_all_summaries(
        summaries_dir=summaries, vault_path=vault, lang="zh"
    )

    assert result.skipped == (name,)
    assert result.exported == ()
    assert (target_dir / name).read_text(encoding="utf-8") == "KEEP MY EDIT\n"


def test_export_all_ignores_bad_filenames(tmp_path):
    summaries = tmp_path / "summaries"
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_summary(summaries, "random.md", "x\n")
    _write_summary(summaries, "summary-2026-05-25_2026-05-31.md", "ok\n")

    result = export_all_summaries(
        summaries_dir=summaries, vault_path=vault, lang="en"
    )

    assert result.exported == ("summary-2026-05-25_2026-05-31.md",)
    assert not (vault / "Talky" / "random.md").exists()


def test_export_all_empty_dir(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    result = export_all_summaries(
        summaries_dir=tmp_path / "summaries", vault_path=vault, lang="en"
    )
    assert result == ExportResult()


def test_export_all_leaves_no_tmp_files(tmp_path):
    summaries = tmp_path / "summaries"
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_summary(summaries, "summary-2026-05-25_2026-05-31.md", "ok\n")
    export_all_summaries(summaries_dir=summaries, vault_path=vault, lang="en")
    assert list((vault / "Talky").glob("*.tmp")) == []


def test_run_export_vault_not_set(tmp_path):
    settings = SimpleNamespace(obsidian_vault_path="", ui_locale="en")
    result = run_export(settings, tmp_path / "summaries")
    assert result.error == "vault_not_set"


def test_run_export_vault_missing(tmp_path):
    settings = SimpleNamespace(
        obsidian_vault_path=str(tmp_path / "nope"), ui_locale="en"
    )
    result = run_export(settings, tmp_path / "summaries")
    assert result.error == "vault_missing"


def test_run_export_happy_path_maps_locale(tmp_path):
    summaries = tmp_path / "summaries"
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_summary(summaries, "summary-2026-05-25_2026-05-31.md", "ok\n")
    settings = SimpleNamespace(obsidian_vault_path=str(vault), ui_locale="mixed")
    result = run_export(settings, summaries)
    assert result.error is None
    assert result.exported == ("summary-2026-05-25_2026-05-31.md",)
    # ui_locale "mixed" -> lang "zh" -> Chinese tag
    text = (vault / "Talky" / "summary-2026-05-25_2026-05-31.md").read_text("utf-8")
    assert "tags: [Talky, 周报]" in text
