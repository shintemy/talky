# Dual-Trigger Hotkey: Fn + External Keypad (Ctrl+Shift+Option)

- **Date:** 2026-06-02
- **Status:** Approved (design), pending implementation plan
- **Branch:** `feature/dual-trigger-hotkey`
- **Scope owner:** sean

## Problem

Talky records while a single hold-to-talk hotkey is held (default: Mac **Fn**,
configured via `AppSettings.hotkey`). The user has an external **EleksMaker
EM-TouchFish III** programmable keypad (USB Type-C) and wants one of its keys to
*also* trigger recording, **simultaneously** with the built-in Fn key — both
valid at the same time, neither disabling the other.

## Empirical findings (probe data, 2026-06-02)

A throwaway read-only Quartz event-tap probe (`/tmp/talky_key_probe.py`, listening
to `keyDown` / `keyUp` / `flagsChanged`) captured what the hardware actually emits.
This drove every decision below.

1. **Mac Fn** → `flagsChanged` with `kCGEventFlagMaskSecondaryFn` set. This is
   exactly what Talky's existing Fn path consumes. ✅
2. **EleksMaker key, default config** → a **macro burst**: `Cmd+A` then `Cmd+C`
   (select-all + copy), modifiers released after ~0.6s regardless of how long the
   key is physically held. A macro burst has **no sustained "held" state** → cannot
   drive hold-to-talk, and `Cmd+A/Cmd+C` has destructive side effects.
3. **EleksMaker key, reconfigured via the "标准键盘 / Standard Keyboard" tab to a
   held key-combo (`Shift+Option+Space`)** → the combo is **sustained for the full
   hold**: `mods=shift+alt/opt` persisted from press to release (no clearing
   in between); `Space` even auto-repeated (`keyDown` every ~84ms), with the single
   `keyUp` only arriving on physical release. This proves the "Standard Keyboard"
   mode produces a **true held combination**, suitable for hold-to-talk. ✅

### Consequences of the data

- The keypad **can** sustain a held modifier combo → hold-to-talk is achievable.
- `Space` in the combo is harmful: while recording, the focused app receives a
  stream of (non-breaking, due to `Option+Space`) spaces. The final combo must be
  **pure modifiers** (types nothing).
- `Shift+Option` alone is a common word-selection chord → high false-trigger risk.
  Adding `Ctrl` (→ `Ctrl+Shift+Option`) yields a chord that is **inert when held
  alone** and **rarely pressed by accident**.
- The EleksMaker "Standard Keyboard" tab only exposes `F1`–`F12` (no `F13`–`F24`),
  so a single dedicated `F13`-style key is not available on this hardware; a
  pure-modifier chord is the cleanest reachable option.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Keypad trigger style | **Hold-to-talk** (same as Fn) | User preference; hardware confirmed capable of sustained hold. |
| Keypad chord | **`Ctrl+Shift+Option`** (no `Cmd`, no regular key) | Inert when held alone; types nothing; rarely pressed by accident; no `Cmd` → no system-shortcut collision. |
| Configurable vs fixed | **Hard-coded** (no UI, no setting) | User chose minimal footprint. A toggle can be added later (YAGNI). |
| Concurrency model | **One event tap, multiple match conditions** | Both Fn and `Ctrl+Shift+Option` arrive via `flagsChanged`, so a single tap can match either. Keeps one thread / one health-check; preserves existing tests that assume a single tap + callback. |
| Always-on? | Secondary chord active for **all** users, regardless of keypad presence | Inert + rare → negligible false-trigger risk; avoids a config surface. |

### Collision check (verified)

- Existing `GlobalShortcutListener` (opens Settings) = **`Cmd+Option+Ctrl`**
  (`talky/ui.py:2776`). The new chord is `Ctrl+Shift+Option` (has `Shift`, no `Cmd`)
  → **no overlap**.
- `_validate_custom_hotkey` already accepts arbitrary multi-modifier sets
  (`talky/ui.py:2425`), and `_mods_from_flags` already decodes `ctrl/shift/alt`
  (`talky/hotkey.py:181`). The chord is fully representable today; the only missing
  capability is running it **concurrently** with the primary hotkey.

## Architecture

All code changes are confined to **`talky/hotkey.py`**. No changes to
`models.py` (settings), `controller.py`, or the UI.

### Current state (as-is)

- `HoldToTalkHotkey(key_mode, custom_keys, on_press, on_release)` listens via a
  single Quartz `flagsChanged` event tap and matches **one** required-modifier set
  derived from `key_mode`.
- Two near-duplicate start methods exist: `_start_fn_quartz_listener` and
  `_start_modifier_quartz_listener`.
- Only modifier-flag changes are observed (no `keyDown`/`keyUp`). `fn` is itself a
  modifier flag (`kCGEventFlagMaskSecondaryFn`).

### Target state (to-be)

1. **Multi-condition matching on one tap.** `start()` builds a list of required
   modifier-sets, `conditions: list[set[str]]`:
   - **Primary** from existing `key_mode` logic (e.g. `fn → {"fn"}`, with the
     existing fallback to `{"alt"}` when `SecondaryFn` is unavailable; `right_option
     → {"alt"}`; `custom → recorded set`; etc.).
   - **Secondary (hard-coded):** `{"ctrl", "shift", "alt"}`.
2. **Unify the two start methods** into a single `_start_quartz_listener(conditions)`.
   The callback, on `flagsChanged`, computes
   `current = _mods_from_flags(flags)` and
   `pressed = any(cond.issubset(current) for cond in conditions)`.
   - Rising edge (`not _pressed → pressed`) → `on_press()`.
   - Falling edge (`pressed → not _pressed`) → `on_release()`.
3. **Combined state is a single boolean** (`self._pressed`). OR semantics fall out
   naturally: holding Fn then also pressing the keypad chord does not re-fire
   `on_press`; releasing one while the other is still held keeps `_pressed` true;
   only when **no** condition matches does `on_release` fire.
4. **Startup seed** keeps the existing phantom-press guard, generalized:
   `self._pressed = any(cond.issubset(current_mods_at_start))`.
5. **`is_pressed_now()`** generalized to `any(cond.issubset(current))` over the
   conditions list.

### Pure, testable core

Extract a side-effect-free helper so the matching/edge logic is unit-testable
without Quartz, e.g.:

```
def evaluate(conditions, current_mods, prev_pressed) -> (new_pressed, fire_press, fire_release)
```

The Quartz callback becomes a thin wrapper that calls `evaluate(...)` and invokes
the `on_press` / `on_release` callbacks.

### Explicitly unchanged (minimal blast radius)

- `HoldToTalkHotkey.__init__` signature → existing tests construct it unchanged.
- Single tap / single thread → `controller.py` wake-guard, `is_healthy()`,
  `ensure_active()`, `using_fallback` all untouched.
- `AppSettings` and the settings UI → no new fields, no new controls.

## Behavior matrix

| User action | `_pressed` transitions | Callback |
|---|---|---|
| Hold Fn | `false → true` on Fn down | `on_press`; `on_release` on Fn up |
| Hold keypad chord | `false → true` on chord complete | `on_press`; `on_release` on release |
| Hold Fn, then add chord, release Fn, then release chord | stays `true` across the middle transitions | **single** `on_press`, **single** `on_release` (at final release) |
| System reports chord/Fn already held at startup | seeded `true` | no phantom `on_press` |

## Testing

Add to `tests/test_hotkey.py` (or a sibling), using the existing fake-Quartz
harness where a tap is needed, and direct calls to the pure `evaluate(...)` helper
where it is not:

1. **Fn only** — Fn down → 1 press; Fn up → 1 release.
2. **Keypad chord only** — `ctrl+shift+alt` down → 1 press; clear → 1 release.
3. **OR overlap** — Fn down (press), add `ctrl+shift+alt` (no second press),
   release Fn (no release, chord still held), release chord (1 release). Net: 1
   press, 1 release.
4. **Startup seed** — chord/Fn already held at start → first matching event fires
   **no** press; subsequent clear fires release. (Mirrors the existing
   `test_hold_to_talk_fn_does_not_fire_when_initially_pressed`.)
5. **Regression** — full `tests/test_hotkey.py` and
   `tests/test_controller_hotkey_threading.py` pass unchanged.

## Manual prerequisite (hardware, not code)

In the EleksMaker **EM-TouchFish III** configurator → **标准键盘 / Standard
Keyboard** tab, set the target key to **`Ctrl + Shift + Opt`** (remove `Space`, add
`Ctrl`), then **写入设备 / Write to device**. This removes the space-spam side
effect and matches the hard-coded chord.

## Acceptance (human-flow first)

1. Unit tests green (`pytest tests/test_hotkey.py tests/test_controller_hotkey_threading.py`).
2. Run Talky: hold **Fn** → records; release → stops (no regression).
3. Hold the reconfigured **keypad key** → records; release → stops.
4. Hold both, release one then the other → recording continues until **both** are
   released.
5. Hold `Ctrl+Shift+Option` while focused in a text field → **no characters typed**
   (chord is inert) and recording is the only effect.

## Out of scope (YAGNI)

- A settings UI / toggle for the secondary trigger.
- Per-device (IOKit HID) identification — the chord approach needs none.
- Toggle (tap-to-start/stop) mode — hold-to-talk was chosen.
- Supporting non-modifier keypad keys (would require `keyDown`/`keyUp` taps).
