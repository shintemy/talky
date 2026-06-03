# Obsidian Weekly-Summary Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual "Export Weekly Reports to Obsidian" button in the Configs tab that syncs all not-yet-exported weekly summaries (`~/.talky/summaries/summary-*.md`) into `<vault>/Talky/` with YAML front-matter.

**Architecture:** A new pure module `talky/obsidian_export.py` holds all logic (parse filename → date range, build front-matter, copy with dedup-by-existence). The controller exposes one thin method delegating to that module. The Configs tab gets a vault-path picker + export button. `AppSettings` gains one field `obsidian_vault_path`.

**Tech Stack:** Python 3, dataclasses, pathlib, PyQt (Qt Widgets), pytest. macOS desktop app.

**Spec:** `docs/superpowers/specs/2026-06-03-obsidian-weekly-export-design.md`

**Test runner:** `.venv/bin/python -m pytest` — MUST use the `-m` form (run from the project root `/Users/sean/Documents/MyProject/talky`). The project has no `pyproject.toml`/`pytest.ini` and `talky` is not installed as a package, so the bare `.venv/bin/pytest` console script fails with `ModuleNotFoundError: No module named 'talky'`. The `python -m pytest` form puts the project root on `sys.path`.

---

## File Structure

**Create:**
- `talky/obsidian_export.py` — pure logic: `parse_summary_range`, `build_front_matter`, `prepend_front_matter`, `ExportResult`, `export_all_summaries`, `run_export`. No Qt, no clock.
- `tests/test_obsidian_export.py` — unit tests for the above.

**Modify:**
- `talky/models.py` — `AppSettings` gains `obsidian_vault_path: str = ""` + `from_dict` line.
- `talky/controller.py` — import + thin method `export_weekly_summaries_to_obsidian()`.
- `talky/ui.py` — `ConfigsTab`: add `QFileDialog` import, Obsidian section widgets, picker/export handlers, and wire into `collect_settings` / `load_from_settings` / `_apply_locale_texts` / `_save_settings`; add `_ZH` strings.
- `tests/test_config_store.py` — round-trip test for `obsidian_vault_path` (added in Task 3).

**Do NOT touch:** `talky/weekly_summary.py` (generation logic), `talky-server/`, other tabs.

---

### Task 1: Pure module — filename parsing & front-matter

**Files:**
- Create: `talky/obsidian_export.py`
- Test: `tests/test_obsidian_export.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_obsidian_export.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_obsidian_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'talky.obsidian_export'`

- [ ] **Step 3: Create the module with parsing + front-matter**

Create `talky/obsidian_export.py`:

```python
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
    """Parse 'summary-START_END.md' into (start, end); None if it does not match."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_obsidian_export.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add talky/obsidian_export.py tests/test_obsidian_export.py
git commit -m "feat: obsidian_export filename parsing + front-matter builder"
```

---

### Task 2: Pure module — ExportResult, export_all_summaries, run_export

**Files:**
- Modify: `talky/obsidian_export.py`
- Test: `tests/test_obsidian_export.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_obsidian_export.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_obsidian_export.py -v`
Expected: FAIL with `ImportError: cannot import name 'ExportResult'` (and `export_all_summaries`, `run_export`).

- [ ] **Step 3: Add ExportResult, atomic write, export_all_summaries, run_export**

Append to `talky/obsidian_export.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_obsidian_export.py -v`
Expected: PASS (15 passed)

- [ ] **Step 5: Commit**

```bash
git add talky/obsidian_export.py tests/test_obsidian_export.py
git commit -m "feat: obsidian_export export_all_summaries + run_export"
```

---

### Task 3: AppSettings.obsidian_vault_path field

**Files:**
- Modify: `talky/models.py:60` (field), `talky/models.py:88` (`from_dict`)
- Test: `tests/test_config_store.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config_store.py` (imports `AppSettings` from `talky.models` — confirm the existing import at the top of that test file; add `from talky.models import AppSettings` if not present):

```python
def test_obsidian_vault_path_round_trips():
    from talky.models import AppSettings

    s = AppSettings(obsidian_vault_path="/Users/me/Vault")
    assert s.to_dict()["obsidian_vault_path"] == "/Users/me/Vault"
    restored = AppSettings.from_dict(s.to_dict())
    assert restored.obsidian_vault_path == "/Users/me/Vault"


def test_obsidian_vault_path_defaults_empty():
    from talky.models import AppSettings

    assert AppSettings.from_dict({}).obsidian_vault_path == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config_store.py -k obsidian -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'obsidian_vault_path'`

- [ ] **Step 3: Add the field and from_dict line**

In `talky/models.py`, in the `AppSettings` dataclass body (after `wake_guard_suspected_false_positive_count: int = 0` at line 85), add:

```python
    obsidian_vault_path: str = ""
```

In `AppSettings.from_dict`, inside the `return cls(...)` call (after the `wake_guard_suspected_false_positive_count=...` argument near line 128-130), add:

```python
            obsidian_vault_path=str(data.get("obsidian_vault_path", "")),
```

(`to_dict` uses `asdict` — no change. `settings_for_disk` uses `replace` — no change.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_config_store.py -k obsidian -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add talky/models.py tests/test_config_store.py
git commit -m "feat: AppSettings.obsidian_vault_path field"
```

---

### Task 4: Controller method

**Files:**
- Modify: `talky/controller.py:65-69` (import), and add method near `_run_weekly_summary_async` (around `controller.py:602`)

> No separate unit test: this method is a 1-line delegation to `run_export`, which is fully tested in Task 2; the AppController is heavy to instantiate. Integration is covered by the manual verification in Task 6.

- [ ] **Step 1: Add the import**

In `talky/controller.py`, immediately after the existing `from talky.weekly_summary import (...)` block (ends at line 69), add:

```python
from talky.obsidian_export import ExportResult, run_export
```

- [ ] **Step 2: Add the method**

In `talky/controller.py`, add this method to the `AppController` class, directly after `_run_weekly_summary_async` (after its `finally:` block around line 623):

```python
    def export_weekly_summaries_to_obsidian(self) -> ExportResult:
        """Sync all weekly summaries into the configured Obsidian vault."""
        return run_export(self.settings, self._summaries_dir)
```

- [ ] **Step 3: Verify it imports cleanly**

Run: `.venv/bin/python -c "import talky.controller; print('ok')"`
Expected: prints `ok` (no ImportError)

- [ ] **Step 4: Commit**

```bash
git add talky/controller.py
git commit -m "feat: controller.export_weekly_summaries_to_obsidian"
```

---

### Task 5: Configs tab — vault picker + export button

**Files:**
- Modify: `talky/ui.py` — import (line ~36), `_ZH` dict (line ~173), `ConfigsTab.__init__` (widgets ~line 1668; section ~line 1960), new handler methods, `collect_settings` (~2065), `load_from_settings` (~2050), `_apply_locale_texts` (~2124), `_save_settings` (~2588)

> UI is not unit-tested in this codebase (consistent with how the weekly-summary feature was shipped). Verified manually in Task 6. Make each edit exactly as shown.

- [ ] **Step 1: Add the QFileDialog import**

In `talky/ui.py`, the Qt widgets import list includes `QMessageBox,` at line 36. Add `QFileDialog,` to that same import list (e.g. on its own line just above `QMessageBox,`):

```python
    QFileDialog,
    QMessageBox,
```

- [ ] **Step 2: Add `_ZH` strings**

In `talky/ui.py`, in the `_ZH` dict (starts line 75), after the `"app_preferences": "应用偏好",` entry (line 173), add:

```python
    "obsidian_sync": "Obsidian 同步",
    "obsidian_choose": "选择 Vault…",
    "obsidian_choose_title": "选择 Obsidian Vault 文件夹",
    "obsidian_export": "导出周报到 Obsidian",
    "obsidian_no_vault": "尚未选择 Vault",
    "obsidian_need_vault": "请先选择你的 Obsidian Vault。",
    "obsidian_vault_missing": "找不到 Vault 文件夹，请重新选择。",
    "obsidian_nothing": "暂无周报可导出。",
    "obsidian_done": "已导出 {n} 份，跳过 {m} 份（已存在）。",
    "obsidian_failed": "失败：{names}",
```

- [ ] **Step 3: Create the Obsidian widgets in `__init__`**

In `ConfigsTab.__init__`, place this block after the `self.ollama_model_combo.currentIndexChanged.connect(...)` setup ends (around line 1668) and before the `def _new_form_grid()` helper (line 1748) — i.e. anywhere in the widget-creation zone, as long as it is after the other widgets are created. Add:

```python
        # ---- Obsidian sync ----
        self._obsidian_vault_path = ""
        self._obsidian_path_label = QLabel("")
        self._obsidian_path_label.setObjectName("WindowSubtitle")
        self._obsidian_path_label.setWordWrap(True)
        self._obsidian_choose_button = QPushButton(
            _tr(self._locale, "Choose Vault…", "obsidian_choose")
        )
        self._obsidian_choose_button.setObjectName("SecondaryButton")
        self._obsidian_choose_button.clicked.connect(self._choose_obsidian_vault)
        self._obsidian_export_button = QPushButton(
            _tr(self._locale, "Export Weekly Reports to Obsidian", "obsidian_export")
        )
        self._obsidian_export_button.setObjectName("PrimaryButton")
        self._obsidian_export_button.clicked.connect(self._export_to_obsidian)
```

- [ ] **Step 4: Add the Obsidian section to the layout**

In `ConfigsTab.__init__`, after the App Preferences section is added (`content_layout.addWidget(self._app_section)` at line 1960) and before `content_layout.addStretch()` (line 1962), add:

```python
        self._obsidian_section = QFrame()
        self._obsidian_section.setObjectName("SectionFrame")
        ob_layout = QVBoxLayout(self._obsidian_section)
        ob_layout.setContentsMargins(16, 14, 16, 14)
        ob_layout.setSpacing(10)
        self._obsidian_card_title = QLabel(
            _tr(self._locale, "Obsidian Sync", "obsidian_sync")
        )
        self._obsidian_card_title.setObjectName("CardTitle")
        ob_layout.addWidget(self._obsidian_card_title)

        ob_path_row = QHBoxLayout()
        ob_path_row.setSpacing(8)
        ob_path_row.addWidget(self._obsidian_choose_button)
        ob_path_row.addWidget(self._obsidian_path_label, 1)
        ob_layout.addLayout(ob_path_row)

        ob_btn_row = QHBoxLayout()
        ob_btn_row.addWidget(self._obsidian_export_button)
        ob_btn_row.addStretch()
        ob_layout.addLayout(ob_btn_row)
        content_layout.addWidget(self._obsidian_section)
```

- [ ] **Step 5: Add the handler methods**

In `ConfigsTab`, add these three methods (place them after `collect_settings`, before `_apply_locale_texts` — around line 2096):

```python
    def _refresh_obsidian_state(self) -> None:
        path = self._obsidian_vault_path.strip()
        if path:
            self._obsidian_path_label.setText(path)
        else:
            self._obsidian_path_label.setText(
                _tr(self._locale, "No vault selected", "obsidian_no_vault")
            )
        self._obsidian_export_button.setEnabled(
            bool(path) and Path(path).is_dir()
        )

    def _choose_obsidian_vault(self) -> None:
        start_dir = self._obsidian_vault_path or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(
            self,
            _tr(self._locale, "Choose Obsidian Vault", "obsidian_choose_title"),
            start_dir,
        )
        if not chosen:
            return
        self._obsidian_vault_path = chosen
        self._refresh_obsidian_state()
        self._save_settings(quiet=True)

    def _export_to_obsidian(self) -> None:
        result = self.controller.export_weekly_summaries_to_obsidian()
        if result.error == "vault_not_set":
            msg = _tr(
                self._locale,
                "Please choose your Obsidian vault first.",
                "obsidian_need_vault",
            )
        elif result.error == "vault_missing":
            msg = _tr(
                self._locale,
                "Vault folder not found. Please choose it again.",
                "obsidian_vault_missing",
            )
        elif not result.exported and not result.skipped:
            msg = _tr(
                self._locale, "No weekly reports to export yet.", "obsidian_nothing"
            )
        else:
            template = _tr(
                self._locale,
                "Exported {n}, skipped {m} (already present).",
                "obsidian_done",
            )
            msg = template.format(n=len(result.exported), m=len(result.skipped))
            if result.failed:
                names = ", ".join(name for name, _ in result.failed)
                failed_tpl = _tr(self._locale, "Failed: {names}", "obsidian_failed")
                msg = msg + "\n" + failed_tpl.format(names=names)
        QMessageBox.information(self, "Talky", msg)
```

- [ ] **Step 6: Wire into `collect_settings`**

In `ConfigsTab.collect_settings` (line 2054), add this key to the returned dict (e.g. after `"llm_debug_stream": False,` at line 2094):

```python
            "obsidian_vault_path": self._obsidian_vault_path,
```

- [ ] **Step 7: Wire into `load_from_settings`**

In `ConfigsTab.load_from_settings`, just before `self._is_loading_settings = False` (line 2052), add:

```python
        self._obsidian_vault_path = settings.obsidian_vault_path
        self._refresh_obsidian_state()
```

- [ ] **Step 8: Wire into `_apply_locale_texts`**

In `ConfigsTab._apply_locale_texts`, after `self._app_card_title.setText(...)` (lines 2122-2124), add:

```python
        self._obsidian_card_title.setText(
            _tr(self._locale, "Obsidian Sync", "obsidian_sync")
        )
        self._obsidian_choose_button.setText(
            _tr(self._locale, "Choose Vault…", "obsidian_choose")
        )
        self._obsidian_export_button.setText(
            _tr(self._locale, "Export Weekly Reports to Obsidian", "obsidian_export")
        )
        self._refresh_obsidian_state()
```

- [ ] **Step 9: Persist in `_save_settings` (CRITICAL — prevents wipe)**

`_save_settings` (line 2533) reconstructs a fresh `AppSettings(...)`. Fields not listed there reset to defaults on every save, so `obsidian_vault_path` MUST be added. In the `AppSettings(...)` constructor (ends at line 2589 with `translation_output_language=...`), add:

```python
            obsidian_vault_path=collected.get("obsidian_vault_path", ""),
```

- [ ] **Step 10: Verify the UI module imports cleanly**

Run: `.venv/bin/python -c "import talky.ui; print('ok')"`
Expected: prints `ok` (no SyntaxError / ImportError)

- [ ] **Step 11: Commit**

```bash
git add talky/ui.py
git commit -m "feat: Configs tab Obsidian vault picker + export button"
```

---

### Task 6: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the whole test suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — all existing tests + the new `tests/test_obsidian_export.py` and the two `test_config_store.py` cases. No failures.

- [ ] **Step 2: Manual smoke test (human-flow, per spec §9)**

1. Ensure at least one summary exists: `ls ~/.talky/summaries/` should list `summary-*.md`. (If none, generate one or hand-create a small `summary-2026-05-25_2026-05-31.md` for testing.)
2. Launch the app (per `LOCAL_OPERATION_MANUAL.md`), open the Dashboard → **Configs** tab → scroll to **Obsidian 同步**.
3. Click **选择 Vault…**, pick a local Obsidian vault folder. Confirm the path shows and the export button enables.
4. Click **导出周报到 Obsidian**. Confirm the dialog reports `已导出 N 份，跳过 0 份（已存在）`.
5. In Obsidian, confirm a `Talky/` folder appeared with `summary-START_END.md` files; open one and confirm the YAML front-matter header (title / date_range / `tags: [Talky, 周报]`) is present and the report body follows.
6. Click export again → dialog reports `跳过 N 份（已存在）`; edit a note in Obsidian, export once more, confirm the edit is NOT overwritten.
7. Reopen Configs after restarting the app → the vault path is still set (persistence check).

- [ ] **Step 3: Final commit (if any verification fixes were needed)**

```bash
git add -A
git commit -m "test: verify Obsidian weekly export end-to-end"
```

---

## Notes for the implementer
- DRY: front-matter language mapping reuses `summary_language_for_locale` from `weekly_summary.py`; `_atomic_write` mirrors the proven pattern from `weekly_summary.py` (kept local to avoid importing a private name across modules).
- YAGNI: subfolder name is hardcoded `Talky`; dedup is existence-based (no state file). Both are deliberate per spec §2/§6.
- Do not modify `talky/weekly_summary.py` — generation stays untouched; this feature only reads its output files.
- Leave the pre-existing `M talky/version_checker.py` working-tree change alone; do not stage it.
