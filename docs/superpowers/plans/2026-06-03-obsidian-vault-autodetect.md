# Obsidian Vault Auto-Detect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a "从 Obsidian 检测" button to the Configs Obsidian-sync section that reads `obsidian.json` to locate the current vault, opens the native folder picker pre-pointed at it, and lets the user confirm (granting powerbox write access).

**Architecture:** New pure module `talky/obsidian_vault.py` reads the Obsidian registry. ConfigsTab gets a detect button; the existing `_choose_obsidian_vault` is refactored to share a `_prompt_vault_dir` helper. No new settings/permissions.

**Tech Stack:** Python 3, pathlib, json, PyQt (QFileDialog native panel), pytest. macOS-only.

**Spec:** `docs/superpowers/specs/2026-06-03-obsidian-vault-autodetect-design.md`

**Test runner:** `.venv/bin/python -m pytest tests/ -q` (the `-m` form from repo root; bare `pytest` fails with ModuleNotFoundError and root-level collection pulls in `worktrees/` copies — always scope to `tests/`).

---

## File Structure
- **Create:** `talky/obsidian_vault.py` (registry read), `tests/test_obsidian_vault.py`.
- **Modify:** `talky/ui.py` — ConfigsTab: detect button + `_prompt_vault_dir` helper + `_detect_obsidian_vault` + refactor `_choose_obsidian_vault` + 3 `_ZH` strings + `_apply_locale_texts` refresh.
- **Do NOT touch:** `talky/obsidian_export.py`, `talky/models.py`, `talky/controller.py`, Info.plist/entitlements, `talky/version_checker.py` (pre-existing unstaged change).

---

### Task 1: Pure module — read Obsidian vault registry

**Files:**
- Create: `talky/obsidian_vault.py`
- Test: `tests/test_obsidian_vault.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_obsidian_vault.py`:

```python
import json
from pathlib import Path

from talky.obsidian_vault import detect_default_vault, obsidian_config_path


def _write_registry(path: Path, vaults: dict) -> None:
    path.write_text(json.dumps({"vaults": vaults}), encoding="utf-8")


def test_config_path_is_macos_application_support():
    p = obsidian_config_path()
    assert p == Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json"


def test_detect_single_open_vault(tmp_path):
    cfg = tmp_path / "obsidian.json"
    _write_registry(cfg, {"a": {"path": "/V/MyVault", "ts": 111, "open": True}})
    assert detect_default_vault(cfg) == "/V/MyVault"


def test_detect_prefers_open_over_newer_ts(tmp_path):
    cfg = tmp_path / "obsidian.json"
    _write_registry(cfg, {
        "a": {"path": "/V/Open", "ts": 100, "open": True},
        "b": {"path": "/V/NewerButClosed", "ts": 999, "open": False},
    })
    assert detect_default_vault(cfg) == "/V/Open"


def test_detect_falls_back_to_newest_ts_when_none_open(tmp_path):
    cfg = tmp_path / "obsidian.json"
    _write_registry(cfg, {
        "a": {"path": "/V/Older", "ts": 100},
        "b": {"path": "/V/Newer", "ts": 200},
    })
    assert detect_default_vault(cfg) == "/V/Newer"


def test_detect_missing_file(tmp_path):
    assert detect_default_vault(tmp_path / "nope.json") is None


def test_detect_malformed_json(tmp_path):
    cfg = tmp_path / "obsidian.json"
    cfg.write_text("{ not json", encoding="utf-8")
    assert detect_default_vault(cfg) is None


def test_detect_empty_vaults(tmp_path):
    cfg = tmp_path / "obsidian.json"
    _write_registry(cfg, {})
    assert detect_default_vault(cfg) is None


def test_detect_skips_entries_without_path(tmp_path):
    cfg = tmp_path / "obsidian.json"
    _write_registry(cfg, {
        "a": {"ts": 999, "open": True},          # no path -> skipped
        "b": {"path": "/V/Good", "ts": 1},
    })
    assert detect_default_vault(cfg) == "/V/Good"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_obsidian_vault.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'talky.obsidian_vault'`.

- [ ] **Step 3: Create the module** — create `talky/obsidian_vault.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


def obsidian_config_path() -> Path:
    """Path to Obsidian's vault registry on macOS."""
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "obsidian"
        / "obsidian.json"
    )


def detect_default_vault(config_path: Path | None = None) -> str | None:
    """Return the path of the current/most-recent Obsidian vault, or None.

    Selection: prefer the vault with open == True; otherwise the one with the
    largest ts. Reads only Application Support (no TCC-protected access).
    Tolerant: missing file / bad JSON / empty vaults / entries without a path
    all yield None (or are skipped).
    """
    path = config_path or obsidian_config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    vaults = data.get("vaults")
    if not isinstance(vaults, dict) or not vaults:
        return None
    best_key: tuple[int, int] | None = None
    best_path: str | None = None
    for entry in vaults.values():
        if not isinstance(entry, dict):
            continue
        vault_path = entry.get("path")
        if not vault_path:
            continue
        key = (1 if entry.get("open") else 0, int(entry.get("ts") or 0))
        if best_key is None or key > best_key:
            best_key = key
            best_path = str(vault_path)
    return best_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_obsidian_vault.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add talky/obsidian_vault.py tests/test_obsidian_vault.py
git commit -m "feat: obsidian_vault registry reader (detect current vault)"
```

---

### Task 2: Configs UI — detect button + shared picker helper

**Files:**
- Modify: `talky/ui.py` (ConfigsTab — import, `_ZH`, widgets ~line 1692, path row ~line 2006, handlers ~line 2156-2179, `_apply_locale_texts` ~line 2240)

> UI is not unit-tested in this codebase. Verify via `import talky.ui` + the full suite + manual smoke (Task 3). Anchor each edit by the code shown, not absolute line numbers.

- [ ] **Step 1: Add the import**

Near the top of `talky/ui.py`, the obsidian_export import already exists? No — ui.py imports from `talky` modules at the top. Add an import for the new module. Find an existing `from talky.` import block near the top of `ui.py` and add:

```python
from talky.obsidian_vault import detect_default_vault
```

(If unsure where, place it alongside other `from talky.<module> import ...` lines at the top of the file.)

- [ ] **Step 2: Add `_ZH` strings**

In the `_ZH` dict, after `"obsidian_choose_title": "选择 Obsidian Vault 文件夹",` add:

```python
    "obsidian_detect": "从 Obsidian 检测",
    "obsidian_detect_confirm_title": "确认 Obsidian Vault",
    "obsidian_detect_none": "没找到 Obsidian 的 vault（请先在 Obsidian 里打开一个 vault）。",
```

- [ ] **Step 3: Create the detect button widget in `__init__`**

Find this existing block (the choose button creation, ~line 1692-1696):
```python
        self._obsidian_choose_button = QPushButton(
            _tr(self._locale, "Choose Vault…", "obsidian_choose")
        )
        self._obsidian_choose_button.setObjectName("SecondaryButton")
        self._obsidian_choose_button.clicked.connect(self._choose_obsidian_vault)
```
Immediately AFTER it, add:

```python
        self._obsidian_detect_button = QPushButton(
            _tr(self._locale, "Detect from Obsidian", "obsidian_detect")
        )
        self._obsidian_detect_button.setObjectName("SecondaryButton")
        self._obsidian_detect_button.clicked.connect(self._detect_obsidian_vault)
```

- [ ] **Step 4: Add the detect button to the path row**

Find this existing block (~line 2006-2010):
```python
        ob_path_row = QHBoxLayout()
        ob_path_row.setSpacing(8)
        ob_path_row.addWidget(self._obsidian_choose_button)
        ob_path_row.addWidget(self._obsidian_path_label, 1)
        ob_layout.addLayout(ob_path_row)
```
Replace the middle so the detect button sits between choose and the label:
```python
        ob_path_row = QHBoxLayout()
        ob_path_row.setSpacing(8)
        ob_path_row.addWidget(self._obsidian_choose_button)
        ob_path_row.addWidget(self._obsidian_detect_button)
        ob_path_row.addWidget(self._obsidian_path_label, 1)
        ob_layout.addLayout(ob_path_row)
```

- [ ] **Step 5: Add the shared helper + refactor `_choose_obsidian_vault` + add `_detect_obsidian_vault`**

Replace the EXISTING `_choose_obsidian_vault` method (currently):
```python
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
```
with these THREE methods:
```python
    def _prompt_vault_dir(self, start_dir: str, title_en: str, title_key: str) -> None:
        # Native panel only (no DontUseNativeDialog) so powerbox grants access
        # to the user-confirmed folder — required to write into an iCloud vault.
        chosen = QFileDialog.getExistingDirectory(
            self, _tr(self._locale, title_en, title_key), start_dir
        )
        if not chosen:
            return
        self._obsidian_vault_path = chosen
        self._refresh_obsidian_state()
        self._save_settings(quiet=True)

    def _choose_obsidian_vault(self) -> None:
        self._prompt_vault_dir(
            self._obsidian_vault_path or str(Path.home()),
            "Choose Obsidian Vault",
            "obsidian_choose_title",
        )

    def _detect_obsidian_vault(self) -> None:
        detected = detect_default_vault()
        if not detected:
            QMessageBox.information(
                self,
                "Talky",
                _tr(
                    self._locale,
                    "Couldn't find an Obsidian vault. Open a vault in Obsidian first.",
                    "obsidian_detect_none",
                ),
            )
            return
        self._prompt_vault_dir(
            detected, "Confirm Obsidian Vault", "obsidian_detect_confirm_title"
        )
```

- [ ] **Step 6: Refresh the detect button text in `_apply_locale_texts`**

Find this existing block in `_apply_locale_texts` (~line 2243-2244):
```python
        self._obsidian_choose_button.setText(
            _tr(self._locale, "Choose Vault…", "obsidian_choose")
        )
```
Immediately AFTER it, add:
```python
        self._obsidian_detect_button.setText(
            _tr(self._locale, "Detect from Obsidian", "obsidian_detect")
        )
```

- [ ] **Step 7: Verify import + full suite**

Run: `.venv/bin/python -c "import talky.ui; print('ok')"` → must print `ok`.
Run: `.venv/bin/python -m pytest tests/ -q` → expect no new failures (baseline `295 passed, 3 xfailed`, now `303 passed, 3 xfailed` after Task 1's 8 tests).

- [ ] **Step 8: Commit**

```bash
git add talky/ui.py
git commit -m "feat: Configs 'Detect from Obsidian' button (locate + confirm vault)"
```

---

### Task 3: Verification

- [ ] **Step 1: Full suite** — `.venv/bin/python -m pytest tests/ -q` → `303 passed, 3 xfailed`, no failures.

- [ ] **Step 2: Manual smoke (human-flow, per spec §7)**
  1. Rebuild/repackage the app (`./scripts/build_unsigned_dmg.sh`) and launch, or run from source.
  2. Configs → Obsidian 同步 → click **从 Obsidian 检测**.
  3. The native folder picker should open **already at your Obsidian vault** (`…/Sean's Obsidian`). Click Open.
  4. Confirm the path fills in and the Export button enables.
  5. Click **导出周报到 Obsidian** → if macOS shows an iCloud-Drive access prompt, allow it → confirm `Talky/` appears in the vault with the weekly report(s).
  6. Negative: there is no easy way to simulate "no Obsidian" on this machine; trust the unit test `test_detect_missing_file`/`test_detect_empty_vaults` for that branch, and confirm the message path by reading the handler.

- [ ] **Step 3: Final commit (if any fixes were needed)**

```bash
git add -A talky/ tests/
git commit -m "test: verify Obsidian vault auto-detect"
```

---

## Notes
- DRY: `_choose_obsidian_vault` and `_detect_obsidian_vault` share `_prompt_vault_dir`.
- No new permissions/entitlements: reading `obsidian.json` (Application Support) needs none; write access to the iCloud vault is granted by powerbox when the user confirms in the native panel.
- Leave the pre-existing `M talky/version_checker.py` and the untracked `tests/test_configs_save_preserves_settings.py` (from the separate spawned task) alone — do not stage them.
