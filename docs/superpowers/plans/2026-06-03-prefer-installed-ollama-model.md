# Prefer Installed Ollama Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop forcing users to download qwen3.5; when any local Ollama model is installed, silently prefer it.

**Architecture:** A single pure resolver `resolve_installed_model` (keep configured if installed; else adopt first installed; else keep configured for the zero-model download suggestion). Wire it into the live paths: controller startup auto-adopts + persists an installed model; mode-switch validation accepts any installed model and auto-binds; plus defensive fixes in the (currently dormant) main-recheck and returning-user-prompt paths.

**Tech Stack:** Python 3.12, PyQt6, Ollama, pytest. Run tests with `.venv/bin/python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-06-03-prefer-installed-ollama-model-design.md`

**Branch:** `claude/blissful-pascal-acf93a` (already checked out; `.venv` symlink present).

**Pre-existing broken tests (baseline, NOT ours):** 8 failed + 3 errors in `test_controller_hotkey_threading.py` (4), `test_onboarding_wizard.py` (3), `test_prompt_tab_persistence.py` (1). T5 will fix 2 of the onboarding ones, so after this plan the baseline shrinks to 6 failed + 3 errors. Completion gate = no NEW failures beyond baseline + all new/updated tests green.

---

## File Structure

**Create:**
- `tests/test_resolve_installed_model.py`

**Modify:**
- `talky/models.py` — add `resolve_installed_model`.
- `talky/controller.py` — add `_auto_adopt_installed_model`, call it from `_warm_up_models`.
- `talky/ui.py` — `_validate_mode_ready` accepts any installed model; `_ensure_llm_mode_ready_or_revert` auto-binds.
- `talky/main.py` — `_deferred_local_ollama_recheck` resolves before readiness.
- `talky/onboarding.py` — `show_returning_user_prompt` "configured missing but others exist" branch → silent auto-bind.
- `tests/test_controller_hotkey_threading.py`, `tests/test_onboarding_wizard.py` — tests.

**Do NOT change:** `RECOMMENDED_OLLAMA_MODEL` (qwen3.5 stays the zero-model recommendation); `run_preflight_check`'s contract.

---

## Task 1: `resolve_installed_model` pure resolver

**Files:**
- Modify: `talky/models.py`
- Test: `tests/test_resolve_installed_model.py`

- [ ] **Step 1: Write the failing test** — Create `tests/test_resolve_installed_model.py`:

```python
from __future__ import annotations

from unittest.mock import patch

from talky.models import resolve_installed_model


def test_keeps_configured_when_installed() -> None:
    with patch("talky.models.list_ollama_models", return_value=["qwen3.5:9b", "gemma4:e2b"]):
        assert resolve_installed_model("qwen3.5:9b") == "qwen3.5:9b"


def test_adopts_other_when_configured_missing() -> None:
    with patch("talky.models.list_ollama_models", return_value=["gemma4:e2b"]):
        assert resolve_installed_model("qwen3.5:9b") == "gemma4:e2b"


def test_keeps_configured_when_no_models() -> None:
    with patch("talky.models.list_ollama_models", return_value=[]):
        assert resolve_installed_model("qwen3.5:9b") == "qwen3.5:9b"


def test_adopts_first_when_configured_empty() -> None:
    with patch("talky.models.list_ollama_models", return_value=["gemma4:e2b", "x:1b"]):
        assert resolve_installed_model("") == "gemma4:e2b"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_resolve_installed_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_installed_model'`.

- [ ] **Step 3: Write minimal implementation** — In `talky/models.py`, add after `detect_ollama_model` (the function around lines 21-24):

```python
def resolve_installed_model(configured: str, host: str = "") -> str:
    """Prefer an installed local model.

    - configured model is installed -> keep it
    - configured missing but other models exist -> adopt the first installed model
    - no models installed -> keep configured (recommended) for the download suggestion
    """
    models = list_ollama_models(host)
    if not models:
        return configured
    configured = (configured or "").strip()
    if configured and configured in models:
        return configured
    return models[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_resolve_installed_model.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add talky/models.py tests/test_resolve_installed_model.py
git commit -m "feat: add resolve_installed_model (prefer installed local model)"
```

---

## Task 2: Controller auto-adopts installed model at startup

**Files:**
- Modify: `talky/controller.py` (import; new `_auto_adopt_installed_model`; call in `_warm_up_models`)
- Test: `tests/test_controller_hotkey_threading.py`

**IMPORTANT:** `tests/test_controller_hotkey_threading.py` has KNOWN pre-existing failures (4 failed + 3 errors). Verify NEW tests via `-k auto_adopt`. Do not modify pre-existing tests in this task.

- [ ] **Step 1: Write the failing test** — Append to `tests/test_controller_hotkey_threading.py`:

```python
def test_auto_adopt_binds_installed_model_when_configured_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _build_controller()
    controller.settings.ollama_model = "qwen3.5:9b"
    monkeypatch.setattr(
        "talky.controller.resolve_installed_model",
        lambda configured, host="": "gemma4:e2b",
    )

    controller._auto_adopt_installed_model()

    assert controller.settings.ollama_model == "gemma4:e2b"
    assert controller.config_store.load().ollama_model == "gemma4:e2b"
    assert controller.llm.model_name == "gemma4:e2b"


def test_auto_adopt_noop_when_model_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = _build_controller()
    controller.settings.ollama_model = "gemma4:e2b"
    monkeypatch.setattr(
        "talky.controller.resolve_installed_model",
        lambda configured, host="": "gemma4:e2b",
    )
    saves: list = []
    monkeypatch.setattr(controller.config_store, "save", lambda s: saves.append(s))

    controller._auto_adopt_installed_model()

    assert controller.settings.ollama_model == "gemma4:e2b"
    assert saves == []


def test_auto_adopt_skips_cloud_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = _build_controller()
    controller.settings.mode = "cloud"
    controller.settings.usage_mode = "vibecoding"
    controller.settings.cloud_api_url = "https://example.com"
    controller.settings.cloud_api_key = "k"
    controller.cloud_service = controller._build_cloud_service()
    calls: list = []
    monkeypatch.setattr(
        "talky.controller.resolve_installed_model",
        lambda *a, **k: calls.append(1) or "x",
    )

    controller._auto_adopt_installed_model()

    assert calls == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_controller_hotkey_threading.py -k auto_adopt -v`
Expected: FAIL — `AttributeError: 'AppController' object has no attribute '_auto_adopt_installed_model'`.

- [ ] **Step 3: Write minimal implementation**

(a) Extend the `talky.models` import (currently `from talky.models import AppSettings, SESSION_START_USAGE_MODE, list_ollama_models`) to add `resolve_installed_model`:

```python
from talky.models import (
    AppSettings,
    SESSION_START_USAGE_MODE,
    list_ollama_models,
    resolve_installed_model,
)
```

(b) Add this method to `AppController` (e.g. just before `_warm_up_models_async`):

```python
    def _auto_adopt_installed_model(self) -> None:
        """If the configured Ollama model isn't installed but others are, adopt an installed one."""
        if self.is_cloud_mode:
            return
        if self.settings.mode not in {"local", "remote"}:
            return
        host = os.environ.get("OLLAMA_HOST", "")
        resolved = resolve_installed_model(self.settings.ollama_model, host)
        if not resolved or resolved == self.settings.ollama_model:
            return
        append_debug_log(
            f"auto-adopt installed ollama model: {self.settings.ollama_model!r} -> {resolved!r}"
        )
        self.settings.ollama_model = resolved
        self.config_store.save(self.settings)
        self.llm = OllamaTextCleaner(
            model_name=resolved, debug_stream=self.settings.llm_debug_stream
        )
        self.settings_updated.emit(self.settings)
```

(c) Call it at the very start of `_warm_up_models` (the method body currently begins with `try:`). Insert BEFORE that existing `try:`:

```python
    def _warm_up_models(self) -> None:
        try:
            self._auto_adopt_installed_model()
        except Exception as exc:
            append_debug_log(f"auto-adopt model failed: {exc}")
        try:
            if should_warm_up_asr():
```

(Keep the rest of `_warm_up_models` unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_controller_hotkey_threading.py -k auto_adopt -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Verify baseline unchanged**

Run: `.venv/bin/python -m pytest tests/test_controller_hotkey_threading.py -q`
Expected: `4 failed, N passed, 3 errors` (same 4 failed + 3 errors as before; N grew by 3).

- [ ] **Step 6: Commit**

```bash
git add talky/controller.py tests/test_controller_hotkey_threading.py
git commit -m "feat: controller auto-adopts an installed Ollama model at startup"
```

---

## Task 3: Mode-switch accepts any installed model + auto-binds

**Files:**
- Modify: `talky/ui.py` (`_validate_mode_ready`, `_ensure_llm_mode_ready_or_revert`)
- Test: `tests/test_configs_permission_refresh.py` (reuse its window-building setup)

**Context:** Read `talky/ui.py` `_ensure_llm_mode_ready_or_revert` (~2255-2298), `_validate_mode_ready` (~2353-2384), and `_populate_ollama_models` (~2166) first. The existing `tests/test_configs_permission_refresh.py` builds a `ConfigsTab` directly with a `SimpleNamespace` controller (see its `test_configs_tab_refreshes_hotkey_when_input_monitoring_granted`); reuse that style. Use a real `AppSettings` as `controller.settings` so all field reads in `__init__` succeed.

- [ ] **Step 1: Write the failing test** — Append to `tests/test_configs_permission_refresh.py` (this file already imports `SimpleNamespace`, `patch`, and has the `qapp` fixture):

```python
def test_validate_mode_ready_accepts_any_installed_model(qapp) -> None:
    from talky.models import AppSettings
    from talky.ui import ConfigsTab

    controller = SimpleNamespace(
        settings=AppSettings(ui_locale="en"),
        refresh_hotkey_listener=lambda: None,
    )
    with (
        patch("talky.ui.check_microphone_granted", return_value=(True, "")),
        patch("talky.ui.check_input_monitoring_granted", return_value=True),
        patch("talky.ui.is_accessibility_trusted", return_value=True),
        patch("talky.models.list_ollama_models", return_value=["gemma4:e2b"]),
    ):
        tab = ConfigsTab(controller=controller, locale="en")
        ok, reason = tab._validate_mode_ready(
            usage_mode="vibecoding",
            mode="local",
            ollama_host="http://127.0.0.1:11434",
            ollama_model="qwen3.5:9b",  # NOT installed, but gemma4 is
        )
    assert ok is True
    assert reason == ""


def test_validate_mode_ready_fails_when_no_models(qapp) -> None:
    from talky.models import AppSettings
    from talky.ui import ConfigsTab

    controller = SimpleNamespace(
        settings=AppSettings(ui_locale="en"),
        refresh_hotkey_listener=lambda: None,
    )
    with (
        patch("talky.ui.check_microphone_granted", return_value=(True, "")),
        patch("talky.ui.check_input_monitoring_granted", return_value=True),
        patch("talky.ui.is_accessibility_trusted", return_value=True),
        patch("talky.models.list_ollama_models", return_value=[]),
    ):
        tab = ConfigsTab(controller=controller, locale="en")
        ok, _reason = tab._validate_mode_ready(
            usage_mode="vibecoding",
            mode="local",
            ollama_host="http://127.0.0.1:11434",
            ollama_model="qwen3.5:9b",
        )
    assert ok is False
```

If `ConfigsTab(...)` construction needs additional patches (e.g. it populates the model combo from `list_ollama_models` in `__init__`), the `talky.models.list_ollama_models` patch above already covers it; add any further patches following the existing test in this file. The `qapp` fixture provides the required `QApplication`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_configs_permission_refresh.py -k validate_mode_ready -v`
Expected: FAIL — `test_validate_mode_ready_accepts_any_installed_model` fails because the current code returns `(False, ...)` when `ollama_model not in models`.

- [ ] **Step 3: Write minimal implementation**

(a) Replace the body of `_validate_mode_ready` — remove the `if ollama_model not in models:` failure block so any installed model passes:

```python
    def _validate_mode_ready(
        self,
        *,
        usage_mode: str,
        mode: str,
        ollama_host: str,
        ollama_model: str,
    ) -> tuple[bool, str]:
        if usage_mode == "daily":
            return True, ""
        if mode == "cloud":
            return True, ""
        if mode not in {"local", "remote"}:
            return False, f"Unsupported mode: {mode}"
        from talky.models import list_ollama_models

        models = list_ollama_models(ollama_host)
        if not models:
            return (
                False,
                "Cannot reach Ollama or no models found on host: "
                f"{ollama_host}\n\n"
                "Please verify host/port and ensure at least one model is installed.",
            )
        return True, ""
```

(b) In `_ensure_llm_mode_ready_or_revert`, after the `if ok:` check, auto-bind the combo to an installed model when the configured one is missing. Replace:

```python
        if ok:
            return True
```

with:

```python
        if ok:
            from talky.models import list_ollama_models, resolve_installed_model

            installed = list_ollama_models(host)
            if installed and model not in installed:
                bound = resolve_installed_model(model, host)
                self._populate_ollama_models(host, preferred_model=bound)
            return True
```

**Verify during implementation:** after `_on_usage_mode_changed` runs to completion (it calls `_populate_ollama_models(host)` again around line 2218-2220 and then `_schedule_quiet_auto_save()`), the bound model must remain selected and persist. Read `_populate_ollama_models` to confirm the later repopulate does not clobber the bound selection (it should select `settings.ollama_model`/preferred). If the later call clobbers it, also set the persisted model (e.g. ensure the combo's preferred selection survives). Add a follow-up assertion test if needed to lock this.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_configs_permission_refresh.py -v`
Expected: PASS (existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add talky/ui.py tests/test_configs_permission_refresh.py
git commit -m "feat: mode-switch accepts any installed Ollama model and auto-binds"
```

---

## Task 4: Startup recheck resolves before nagging (defensive)

**Files:**
- Modify: `talky/main.py` (`_deferred_local_ollama_recheck`, ~429-470)

**Context:** This path early-returns in Daily mode (the launch default), so it is largely dormant; the change is defensive so that if usage mode is LLM at launch, an installed-but-non-configured model is treated as ready. It's a nested closure inside `main()`, so it is verified by reasoning + not breaking `tests/test_main.py` (no new unit test).

- [ ] **Step 1: Read the current function** — Read `talky/main.py` lines ~429-470 (`_deferred_local_ollama_recheck`). Confirm it imports `run_preflight_check`, `OllamaStatus` and calls `run_preflight_check(required_model=s.ollama_model)`.

- [ ] **Step 2: Apply the change** — In `_deferred_local_ollama_recheck`, resolve the model before the readiness check. Change the import line inside the function to also import `resolve_installed_model`, and replace the preflight call. Specifically, where it currently reads:

```python
        from talky.onboarding import OllamaStatus, detect_system_locale, run_preflight_check
        from talky.startup_gate import apply_ollama_host_from_settings

        s = controller.settings
        if s.mode == "cloud":
            return
        if s.usage_mode not in {"vibecoding", "translation"}:
            return
        apply_ollama_host_from_settings(s)
        if run_preflight_check(required_model=s.ollama_model) == OllamaStatus.READY:
            return
```

change the last two lines to resolve first:

```python
        apply_ollama_host_from_settings(s)
        from talky.models import resolve_installed_model

        resolved = resolve_installed_model(s.ollama_model)
        if run_preflight_check(required_model=resolved) == OllamaStatus.READY:
            return
```

(Leave the rest of the function — the tray warning + opening Settings — unchanged. Effect: when any model is installed, `resolved` is an installed model → preflight READY → no nag. Only zero-models / Ollama-down still nags.)

- [ ] **Step 3: Verify no regression**

Run: `.venv/bin/python -m pytest tests/test_main.py -q`
Expected: PASS (no change to test_main.py behavior; same pass/fail counts as before).

- [ ] **Step 4: Commit**

```bash
git add talky/main.py
git commit -m "fix: startup recheck treats any installed model as ready"
```

---

## Task 5: Returning-user prompt silently auto-binds (fixes 2 broken tests)

**Files:**
- Modify: `talky/onboarding.py` (`show_returning_user_prompt`, the `if models and required_model and required_model not in models:` branch ~1083-1165)
- Test: `tests/test_onboarding_wizard.py` (rewrite 2 pre-existing-failing tests to the new behavior)

**Context:** Read `talky/onboarding.py` `show_returning_user_prompt` (~1077-1201). The branch at line ~1083 currently shows a dialog offering "Bind available model" / "Download configured model" (a `do script` pull of the possibly-unsafe configured name). Replace that whole branch with a SILENT auto-bind. This also removes the osascript-injection-via-model-name path and makes 2 currently-failing tests pass after rewrite.

- [ ] **Step 1: Rewrite the 2 affected tests** — In `tests/test_onboarding_wizard.py`, REPLACE `test_show_returning_user_prompt_blocks_unsafe_model_pull` and `test_show_returning_user_prompt_bind_requires_explicit_confirmation` with these (the new behavior: silent auto-bind, no dialog, no Popen):

```python
def test_show_returning_user_prompt_auto_binds_available_model():
    from talky.onboarding import OllamaStatus, show_returning_user_prompt

    store = MagicMock()
    store.load.return_value = MagicMock(
        ollama_host="http://127.0.0.1:11434",
        ollama_model="qwen3.5:9b",
    )
    with (
        patch("talky.onboarding.check_ollama_reachable", return_value=(True, "")),
        patch("talky.onboarding.list_ollama_models", return_value=["gemma4:e2b"]),
        patch("talky.onboarding.subprocess.Popen") as popen,
    ):
        result = show_returning_user_prompt(
            OllamaStatus.NO_MODEL,
            locale="en",
            config_store=store,
            expected_model="qwen3.5:9b",
        )
        assert result is True
        popen.assert_not_called()
        saved_settings = store.save.call_args[0][0]
        assert saved_settings.ollama_model == "gemma4:e2b"


def test_show_returning_user_prompt_auto_binds_even_for_unsafe_configured_name():
    from talky.onboarding import OllamaStatus, show_returning_user_prompt

    store = MagicMock()
    store.load.return_value = MagicMock(ollama_host="http://127.0.0.1:11434")
    with (
        patch("talky.onboarding.check_ollama_reachable", return_value=(True, "")),
        patch("talky.onboarding.list_ollama_models", return_value=["gemma4:e2b"]),
        patch("talky.onboarding.subprocess.Popen") as popen,
    ):
        result = show_returning_user_prompt(
            OllamaStatus.NO_MODEL,
            locale="en",
            config_store=store,
            expected_model="bad;rm -rf /",  # unsafe configured name is never pulled
        )
        assert result is True
        popen.assert_not_called()
        saved_settings = store.save.call_args[0][0]
        assert saved_settings.ollama_model == "gemma4:e2b"
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `.venv/bin/python -m pytest tests/test_onboarding_wizard.py -k "auto_binds" -v`
Expected: FAIL (current branch shows a dialog / does not silently save `gemma4:e2b`).

- [ ] **Step 3: Replace the branch with silent auto-bind** — In `show_returning_user_prompt`, replace the entire block:

```python
    if models and required_model and required_model not in models:
        while True:
            ... (the full dialog loop, lines ~1083-1165) ...
```

with:

```python
    if models and required_model and required_model not in models:
        target_model = models[0]
        settings = config_store.load()
        settings.ollama_model = target_model
        config_store.save(settings)
        os.environ["OLLAMA_HOST"] = (
            (settings.ollama_host or "http://127.0.0.1:11434").strip().rstrip("/")
            or "http://127.0.0.1:11434"
        )
        return True
```

(The "no models at all" branch below it — the recommended-model download suggestion — stays unchanged. After this, `confirm_bind_available_model` may become unused; leave it defined for now to avoid touching unrelated tests.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_onboarding_wizard.py -v`
Expected: the 2 new `auto_binds` tests PASS. Note overall counts: `test_wizard_complete_saves_settings` may still be in the pre-existing-failing set (leave it — it's unrelated to this task, owned by the broken-test cleanup).

- [ ] **Step 5: Commit**

```bash
git add talky/onboarding.py tests/test_onboarding_wizard.py
git commit -m "feat: returning-user prompt silently auto-binds installed model"
```

---

## Task 6: Full regression + verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: failures are ONLY pre-existing ones MINUS the 2 onboarding tests T5 fixed. Target: `6 failed, <more> passed, 3 errors` (the remaining 6: 4 in `test_controller_hotkey_threading.py`, 1 in `test_onboarding_wizard.py` [`test_wizard_complete_saves_settings`], 1 in `test_prompt_tab_persistence.py`). Confirm NONE of the failures are in: `test_resolve_installed_model.py`, the `auto_adopt`/`validate_mode_ready`/`auto_binds` tests, or any file we created/edited's new tests.

- [ ] **Step 2: Live behavior sanity (optional, Ollama running)**

```bash
.venv/bin/python - <<'PY'
from unittest.mock import patch
from talky.models import resolve_installed_model, list_ollama_models
print("installed:", list_ollama_models())
print("configured qwen3.5:9b resolves to:", resolve_installed_model("qwen3.5:9b"))
PY
```

Expected: if only gemma4 is installed, prints `configured qwen3.5:9b resolves to: gemma4:e2b`.

- [ ] **Step 3: Final commit (if any cleanup)**

```bash
git add -A && git commit -m "chore: prefer-installed-model cleanup" || echo "nothing to commit"
```

---

## Notes for the implementer
- TDD throughout: write the test, watch it fail, implement, watch it pass, commit.
- Always use `.venv/bin/python -m pytest`.
- `RECOMMENDED_OLLAMA_MODEL` stays qwen3.5 — it's only the zero-model suggestion now.
- Pre-existing broken tests are NOT yours to fix except the 2 in T5 (which you rewrite to the new behavior). Don't touch the others.
- T3 (ui) and T5 (onboarding) require reading existing test setups to mirror them — do that before writing the tests.
