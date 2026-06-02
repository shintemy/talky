# Dual-Trigger Hotkey Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Talky start/stop recording from **either** the Mac **Fn** key **or** a hard-coded **Ctrl+Shift+Option** chord (emitted by the external EleksMaker keypad), both active simultaneously as hold-to-talk triggers.

**Architecture:** Both Fn and Ctrl+Shift+Option arrive as `flagsChanged` events, so one Quartz event tap can match **either** condition. Refactor `HoldToTalkHotkey` from a single required-modifier set to a **list of conditions** evaluated with OR semantics by a small pure function. The secondary chord `{ctrl, shift, alt}` is appended to whatever the primary `key_mode` resolves to. No changes to settings, controller, or UI.

**Tech Stack:** Python 3.12, PyObjC (`Quartz`, `CoreFoundation`), pytest. macOS-only event tap. Run tests with the project venv: `/Users/sean/Documents/MyProject/talky/.venv/bin/python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-06-02-dual-trigger-hotkey-design.md`

---

## File Structure

- **Modify** `talky/hotkey.py` — add module-level `SECONDARY_CHORD` constant + pure `evaluate()`; refactor `HoldToTalkHotkey` to use a `_conditions: list[set[str]]` list and a single unified `_start_quartz_listener()`, replacing the two near-duplicate `_start_fn_quartz_listener` / `_start_modifier_quartz_listener` methods. `GlobalShortcutListener` is untouched.
- **Create** `tests/test_hotkey_evaluate.py` — pure unit tests for `evaluate()` (no Quartz).
- **Modify** `tests/test_hotkey.py` — add two behavior tests (OR overlap, keypad-chord-only) using the existing fake-Quartz harness. Existing tests must pass unchanged.

**Public surface preserved** (referenced by `talky/controller.py` and `tests/test_controller_hotkey_threading.py`): `HoldToTalkHotkey.__init__(key_mode, custom_keys, on_press, on_release)`, `start()`, `stop()`, `is_pressed_now()`, `is_healthy()`, `ensure_active()`, `using_fallback`. Only the private `_required_modifiers` attribute is renamed to `_conditions`.

---

## Task 1: Pure `evaluate()` helper + `SECONDARY_CHORD` constant

**Files:**
- Modify: `talky/hotkey.py` (add module-level constant + function, after the `label_for_hotkey_tokens` function, before `class HoldToTalkHotkey`)
- Test: `tests/test_hotkey_evaluate.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_hotkey_evaluate.py`:

```python
from __future__ import annotations

from talky.hotkey import SECONDARY_CHORD, evaluate


def test_secondary_chord_is_ctrl_shift_alt() -> None:
    assert SECONDARY_CHORD == frozenset({"ctrl", "shift", "alt"})


def test_rising_edge_fires_press_once() -> None:
    conditions = [{"fn"}, set(SECONDARY_CHORD)]
    pressed, fire_press, fire_release = evaluate(conditions, {"fn"}, False)
    assert (pressed, fire_press, fire_release) == (True, True, False)


def test_held_state_does_not_refire() -> None:
    conditions = [{"fn"}, set(SECONDARY_CHORD)]
    pressed, fire_press, fire_release = evaluate(conditions, {"fn"}, True)
    assert (pressed, fire_press, fire_release) == (True, False, False)


def test_falling_edge_fires_release_once() -> None:
    conditions = [{"fn"}, set(SECONDARY_CHORD)]
    pressed, fire_press, fire_release = evaluate(conditions, set(), True)
    assert (pressed, fire_press, fire_release) == (False, False, True)


def test_or_semantics_secondary_condition_matches() -> None:
    conditions = [{"fn"}, set(SECONDARY_CHORD)]
    # Fn not held, but the full chord is -> pressed via the secondary condition.
    pressed, fire_press, _ = evaluate(conditions, {"ctrl", "shift", "alt"}, False)
    assert pressed is True
    assert fire_press is True


def test_partial_chord_does_not_match() -> None:
    conditions = [{"fn"}, set(SECONDARY_CHORD)]
    # Only ctrl+shift (missing alt) -> no condition satisfied.
    pressed, _, _ = evaluate(conditions, {"ctrl", "shift"}, False)
    assert pressed is False


def test_overlap_stays_pressed_when_one_of_two_releases() -> None:
    conditions = [{"fn"}, set(SECONDARY_CHORD)]
    # Holding Fn AND chord, then Fn releases but chord remains -> still pressed.
    pressed, fire_press, fire_release = evaluate(
        conditions, {"ctrl", "shift", "alt"}, True
    )
    assert (pressed, fire_press, fire_release) == (True, False, False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/sean/Documents/MyProject/talky/.venv/bin/python -m pytest tests/test_hotkey_evaluate.py -v`
Expected: FAIL — `ImportError: cannot import name 'SECONDARY_CHORD'` (and `evaluate`).

- [ ] **Step 3: Add the constant and the pure function**

In `talky/hotkey.py`, insert after the `label_for_hotkey_tokens(...)` function (around line 46) and before `class HoldToTalkHotkey`:

```python
SECONDARY_CHORD: frozenset[str] = frozenset({"ctrl", "shift", "alt"})


def evaluate(
    conditions: list[set[str]],
    current_mods: set[str],
    prev_pressed: bool,
) -> tuple[bool, bool, bool]:
    """Pure trigger-state transition for a hold-to-talk listener.

    `pressed` is True when ANY condition's required modifiers are all currently
    held (OR semantics across conditions). Returns the edge events to fire so the
    Quartz callback stays a thin wrapper.

    Returns: (pressed, fire_press, fire_release)
    """
    pressed = any(cond <= current_mods for cond in conditions)
    fire_press = pressed and not prev_pressed
    fire_release = prev_pressed and not pressed
    return pressed, fire_press, fire_release
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Users/sean/Documents/MyProject/talky/.venv/bin/python -m pytest tests/test_hotkey_evaluate.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
cd /Users/sean/Documents/MyProject/talky
git add talky/hotkey.py tests/test_hotkey_evaluate.py
git commit -m "feat(hotkey): add pure evaluate() + SECONDARY_CHORD constant"
```

---

## Task 2: Refactor `HoldToTalkHotkey` to multi-condition single tap

This replaces the single required-modifier set with `_conditions`, appends the
hard-coded secondary chord, and unifies the two start methods into one. All
existing `tests/test_hotkey.py` tests must still pass, plus two new ones.

**Files:**
- Modify: `talky/hotkey.py` (`HoldToTalkHotkey` only — `__init__`, `start`, `stop`, `is_pressed_now`, and replace `_start_modifier_quartz_listener` + `_start_fn_quartz_listener` with `_start_quartz_listener`; add `_primary_condition` + `_fn_mask_available`)
- Test: `tests/test_hotkey.py` (add two tests)

- [ ] **Step 1: Write the failing behavior tests**

Append to `tests/test_hotkey.py`:

```python
def test_dual_trigger_or_semantics(monkeypatch: pytest.MonkeyPatch) -> None:
    hotkey_mod, quartz_state = _reload_hotkey(monkeypatch)
    q = sys.modules["Quartz"]
    presses: list[str] = []
    releases: list[str] = []
    listener = hotkey_mod.HoldToTalkHotkey(
        key_mode="fn",
        custom_keys=[],
        on_press=lambda: presses.append("p"),
        on_release=lambda: releases.append("r"),
    )
    listener.start()
    cb = quartz_state["callback"]
    assert cb is not None

    fn = q.kCGEventFlagMaskSecondaryFn
    chord = (
        q.kCGEventFlagMaskControl
        | q.kCGEventFlagMaskShift
        | q.kCGEventFlagMaskAlternate
    )
    flags_changed = q.kCGEventFlagsChanged

    cb(None, flags_changed, fn, None)            # Fn down -> press
    cb(None, flags_changed, fn | chord, None)    # add chord while holding Fn -> no 2nd press
    cb(None, flags_changed, chord, None)         # release Fn, chord still held -> no release
    cb(None, flags_changed, 0, None)             # release chord -> release

    assert presses == ["p"]
    assert releases == ["r"]


def test_keypad_chord_triggers_alongside_fn_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hotkey_mod, quartz_state = _reload_hotkey(monkeypatch)
    q = sys.modules["Quartz"]
    presses: list[str] = []
    releases: list[str] = []
    listener = hotkey_mod.HoldToTalkHotkey(
        key_mode="fn",
        custom_keys=[],
        on_press=lambda: presses.append("p"),
        on_release=lambda: releases.append("r"),
    )
    listener.start()
    cb = quartz_state["callback"]
    chord = (
        q.kCGEventFlagMaskControl
        | q.kCGEventFlagMaskShift
        | q.kCGEventFlagMaskAlternate
    )
    cb(None, q.kCGEventFlagsChanged, chord, None)  # chord down -> press (secondary cond)
    cb(None, q.kCGEventFlagsChanged, 0, None)      # release -> release
    assert presses == ["p"]
    assert releases == ["r"]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `/Users/sean/Documents/MyProject/talky/.venv/bin/python -m pytest tests/test_hotkey.py::test_keypad_chord_triggers_alongside_fn_primary -v`
Expected: FAIL — with the current single-condition fn listener, the bare `ctrl+shift+alt` chord does not match, so no press fires (`assert presses == ["p"]` fails).

- [ ] **Step 3: Rename the private state in `__init__`**

In `talky/hotkey.py`, in `HoldToTalkHotkey.__init__`, replace:

```python
        self._required_modifiers: set[str] = set()
```

with:

```python
        self._conditions: list[set[str]] = []
```

- [ ] **Step 4: Replace `start()` and add the two helpers**

Replace the entire `start()` method (currently the block from `def start(self) -> None:` through the final `self._start_modifier_quartz_listener(required={"alt"})`) with:

```python
    def start(self) -> None:
        self._using_fallback = False
        primary = self._primary_condition()
        self._conditions = [primary, set(SECONDARY_CHORD)]
        self._start_quartz_listener(self._conditions)

    def _primary_condition(self) -> set[str]:
        """Resolve the user-configured primary hotkey into a required-modifier set."""
        if self.key_mode == "fn":
            if self._fn_mask_available():
                return {"fn"}
            # Standalone Fn unavailable on this OS build -> fall back to Right Option.
            self._using_fallback = True
            return {"alt"}
        if self.key_mode == "right_option":
            return {"alt"}
        if self.key_mode == "right_command":
            return {"cmd"}
        if self.key_mode == "command_option":
            return {"cmd", "alt"}
        if self.key_mode == "custom":
            supported = {"alt", "cmd", "ctrl", "shift", "fn"}
            required = {k for k in self.custom_keys if k in supported}
            return required or {"alt"}
        return {"alt"}

    @staticmethod
    def _fn_mask_available() -> bool:
        try:
            import Quartz

            return getattr(Quartz, "kCGEventFlagMaskSecondaryFn", None) is not None
        except Exception:
            return False
```

- [ ] **Step 5: Update `stop()` to clear `_conditions`**

In `stop()`, replace:

```python
        self._required_modifiers = set()
```

with:

```python
        self._conditions = []
```

- [ ] **Step 6: Generalize `is_pressed_now()`**

Replace the whole `is_pressed_now` method with:

```python
    def is_pressed_now(self) -> bool:
        """Read current modifier state directly; fall back to last callback state."""
        if not self._conditions:
            return self._pressed
        try:
            import Quartz

            source_state = getattr(Quartz, "kCGEventSourceStateCombinedSessionState", 0)
            flags = Quartz.CGEventSourceFlagsState(source_state)
            current = self._mods_from_flags(flags, Quartz)
            return any(cond <= current for cond in self._conditions)
        except Exception:
            return self._pressed
```

- [ ] **Step 7: Replace both start-listener methods with one unified method**

Delete the entire `_start_modifier_quartz_listener(self, required)` method **and** the entire `_start_fn_quartz_listener(self)` method, and replace them with this single method:

```python
    def _start_quartz_listener(self, conditions: list[set[str]]) -> None:
        try:
            import Quartz
            from CoreFoundation import CFRunLoopGetCurrent, CFRunLoopRun
        except Exception:
            return

        tap_disabled_timeout = getattr(Quartz, "kCGEventTapDisabledByTimeout", None)
        tap_disabled_user_input = getattr(Quartz, "kCGEventTapDisabledByUserInput", None)

        # Seed pressed state from current flags to avoid a startup false-positive
        # when a modifier is already held (or stale across sleep/wake).
        try:
            source_state = getattr(Quartz, "kCGEventSourceStateCombinedSessionState", 0)
            current_flags = Quartz.CGEventSourceFlagsState(source_state)
        except Exception:
            current_flags = 0
        current_mods = self._mods_from_flags(current_flags, Quartz)
        self._pressed = any(cond <= current_mods for cond in conditions)

        def _run_event_tap() -> None:
            tap_ref = {"tap": None}

            def _callback(proxy, event_type, event, refcon):
                del proxy, refcon
                if event_type in {tap_disabled_timeout, tap_disabled_user_input}:
                    tap = tap_ref["tap"]
                    if tap is not None:
                        try:
                            Quartz.CGEventTapEnable(tap, True)
                        except Exception:
                            pass
                    return event
                if event_type != Quartz.kCGEventFlagsChanged:
                    return event

                flags = Quartz.CGEventGetFlags(event)
                current = self._mods_from_flags(flags, Quartz)
                pressed, fire_press, fire_release = evaluate(
                    conditions, current, self._pressed
                )
                self._pressed = pressed
                if fire_press:
                    self.on_press()
                elif fire_release:
                    self.on_release()
                return event

            mask = Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly,
                mask,
                _callback,
                None,
            )
            tap_ref["tap"] = tap
            if tap is None:
                return
            self._tap = tap

            source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            run_loop = CFRunLoopGetCurrent()
            self._run_loop = run_loop
            Quartz.CFRunLoopAddSource(run_loop, source, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)
            CFRunLoopRun()

        self._quartz_thread = threading.Thread(target=_run_event_tap, daemon=True)
        self._quartz_thread.start()
```

> Note: This drops the old fn-path "retry as modifier listener when `CGEventTapCreate` returns `None`" branch. A `None` tap means the OS denied the tap (permission/environment); retrying the identical call cannot succeed, so the unified method gives up cleanly. The wake-guard in `controller.py` already rebuilds the listener on health-check failure, so recovery is preserved.

- [ ] **Step 8: Run the full hotkey suite**

Run: `/Users/sean/Documents/MyProject/talky/.venv/bin/python -m pytest tests/test_hotkey.py tests/test_hotkey_evaluate.py -v`
Expected: PASS — all original tests (`..._reenables_event_tap_after_timeout`, `..._stop_joins_quartz_thread`, `..._fn_does_not_fire_when_initially_pressed`, `..._ensure_active_*`, the two `GlobalShortcutListener` tests) plus the two new tests (`test_dual_trigger_or_semantics`, `test_keypad_chord_triggers_alongside_fn_primary`).

- [ ] **Step 9: Commit**

```bash
cd /Users/sean/Documents/MyProject/talky
git add talky/hotkey.py tests/test_hotkey.py
git commit -m "feat(hotkey): dual trigger — Fn + hard-coded Ctrl+Shift+Option chord"
```

---

## Task 3: Full regression + manual verification

**Files:** none (verification only)

- [ ] **Step 1: Run the controller hotkey threading tests (public-surface regression)**

Run: `/Users/sean/Documents/MyProject/talky/.venv/bin/python -m pytest tests/test_controller_hotkey_threading.py -v`
Expected: PASS (the `using_fallback` / `is_pressed_now` SimpleNamespace mocks at lines 246/260 still match the preserved public API).

- [ ] **Step 2: Run the entire test suite**

Run: `/Users/sean/Documents/MyProject/talky/.venv/bin/python -m pytest -q`
Expected: PASS (no regressions). If unrelated pre-existing failures appear, note them but do not fix in this plan.

- [ ] **Step 3: Reconfigure the EleksMaker key (hardware, manual)**

In the EleksMaker **EM-TouchFish III** configurator → **标准键盘 / Standard Keyboard** tab, set the target key to **`Ctrl + Shift + Opt`** (remove `Space`, add `Ctrl`), then click **写入设备 / Write to device**.

Optional re-probe to confirm the emitted chord and inertness:
Run: `/Users/sean/Documents/MyProject/talky/.venv/bin/python /tmp/talky_key_probe.py` (own terminal), hold the key 2s.
Expected: `flagsChange ... mods=ctrl`, then `mods=ctrl+shift+alt`, sustained until release; **no `keyDown` for a printable key** (no Space). (The probe is a throwaway in `/tmp`, not part of the repo.)

- [ ] **Step 4: Manual app verification (human-flow)**

Launch Talky from this branch and confirm:
1. Hold **Fn** → recording starts; release → stops. (No regression.)
2. Hold the reconfigured **keypad key** → recording starts; release → stops.
3. Hold **both**, release one then the other → recording continues until **both** are released.
4. With a text field focused, hold `Ctrl+Shift+Option` → **no characters are typed** (chord is inert); recording is the only effect.

- [ ] **Step 5: Finish the branch**

Use the `superpowers:finishing-a-development-branch` skill to choose merge / PR / cleanup for `feature/dual-trigger-hotkey`.

---

## Self-Review

- **Spec coverage:** Hold-to-talk both triggers (Task 2 + manual Step 4); chord = Ctrl+Shift+Option (Task 1 constant); hard-coded / no UI / no settings change (only `talky/hotkey.py` touched); single tap / public surface preserved (Task 2 Steps 3–7, Task 3 Step 1); OR semantics + startup seed (Task 1 + Task 2 tests); no collision with `Cmd+Option+Ctrl` (chord differs; verified in spec); EleksMaker reconfigure + acceptance (Task 3 Steps 3–4). All spec sections map to a task.
- **Placeholder scan:** No TBD/TODO; every code step shows complete code; every command shows expected output.
- **Type consistency:** `_conditions: list[set[str]]` used consistently across `__init__`, `start`, `stop`, `is_pressed_now`, `_start_quartz_listener`; `evaluate(conditions, current_mods, prev_pressed) -> (pressed, fire_press, fire_release)` signature identical in Task 1 definition and Task 2 callback usage; `SECONDARY_CHORD` referenced identically; `_primary_condition()` / `_fn_mask_available()` defined and called in `start()`.
