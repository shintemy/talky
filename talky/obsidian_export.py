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


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


@dataclass(frozen=True)
class ExportResult:
    exported: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    failed: tuple[tuple[str, str], ...] = ()
    error: str | None = None  # "vault_not_set" | "vault_missing" | None


def export_all_summaries(
    *,
    summaries_dir: Path,
    vault_path: Path,
    lang: str,
    subfolder: str = DEFAULT_SUBFOLDER,
) -> ExportResult:
    """Sync every summary-*.md from summaries_dir into <vault>/<subfolder>/.

    - target already exists -> skipped (never overwrite; protects user edits)
    - otherwise -> prepend front-matter + atomic write -> exported
    - filename not matching SUMMARY_RE -> ignored
    - per-file OSError -> recorded in failed, others continue
    """
    target_dir = vault_path / subfolder
    exported: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []
    try:
        names = sorted(p.name for p in summaries_dir.glob("summary-*.md"))
    except OSError:
        names = []
    for name in names:
        rng = parse_summary_range(name)
        if rng is None:
            continue
        target = target_dir / name
        if target.exists():
            skipped.append(name)
            continue
        try:
            body = (summaries_dir / name).read_text(encoding="utf-8")
            content = prepend_front_matter(body, rng[0], rng[1], lang=lang)
            _atomic_write(target, content)
            exported.append(name)
        except OSError as exc:
            failed.append((name, str(exc)))
    return ExportResult(tuple(exported), tuple(skipped), tuple(failed))


def run_export(settings, summaries_dir: Path) -> ExportResult:
    """Validate settings.obsidian_vault_path and export. settings is duck-typed:
    needs .obsidian_vault_path (str) and .ui_locale (str)."""
    raw = (getattr(settings, "obsidian_vault_path", "") or "").strip()
    if not raw:
        return ExportResult(error="vault_not_set")
    vault = Path(raw)
    if not vault.is_dir():
        return ExportResult(error="vault_missing")
    lang = summary_language_for_locale(settings.ui_locale)
    return export_all_summaries(
        summaries_dir=summaries_dir, vault_path=vault, lang=lang
    )
