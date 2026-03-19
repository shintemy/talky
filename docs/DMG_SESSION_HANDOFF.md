# DMG Prototype Session Handoff (2026-03-20)

## Branch & Workspace

- **Branch:** `feature/dmg-unsigned-prototype`
- **Worktree:** `.worktrees/feature-dmg-unsigned-prototype`
- **Base commit:** `3084a96` (main)
- **Latest build:** `release/Talky-0.2.1-slim.1-unsigned.dmg`
- **Status:** Phase 1 acceptance checklist passing; DMG size reduced from 264 MB to 108 MB

---

## Session 3 — DMG Size Reduction (2026-03-20)

### What Was Done

Excluded unused transitive dependencies from PyInstaller bundle to reduce DMG size by 59%.

### Changes

| File | Change |
|------|--------|
| `scripts/build_unsigned_dmg.sh` | Added `--exclude-module torch llvmlite scipy numba` to PyInstaller command |

### Size Comparison

| Metric | Before | After | Reduction |
|--------|--------|-------|-----------|
| DMG (compressed) | 264 MB | 108 MB | -59% |
| .app (uncompressed) | 739 MB | 273 MB | -63% |

### Rationale

These packages are transitive dependencies of `mlx-whisper` but never used at runtime — MLX handles inference natively. No project source file imports torch, llvmlite, scipy, or numba.

| Package | Size removed | Pulled by |
|---------|-------------|-----------|
| torch | ~285 MB | mlx-whisper (unused — MLX handles inference) |
| llvmlite | ~111 MB | numba → mlx-whisper |
| scipy | ~38 MB | mlx-whisper |
| numba | ~2 MB | mlx-whisper |

### Verification Required

- [ ] Full round trip: install from DMG → launch → record → ASR → LLM → paste

---

## Session 2 — Native macOS UI Overhaul (2026-03-20)

### What Was Done

Complete redesign of the Dashboard UI from iPad/iOS style to native macOS HIG-compliant appearance.

### UI Changes Summary

| Area | Before | After |
|------|--------|-------|
| Window | `#RootView` gray gradient container, 24px radius, inner padding | Native window background, no wrapper container |
| Tab bar | `#TabBarContainer` pill-shaped tabs, orange background on active | `#SegmentedBar` segmented control, white background + orange text on active |
| Stylesheet | `IOS26_STYLESHEET` — oversized radii, glass cards, gradient bg | `NATIVE_STYLESHEET` — system font, 5px radii, macOS system colors |
| Form controls | 16px border-radius, custom padding | 5px border-radius, native `QLineEdit`/`QComboBox`/`QSpinBox` look |
| Hotkey config | `QComboBox` + 3 fake buttons (Record/Recommended/Reset) | `QRadioButton` group with keycap badges (fn, ⌥, ⌘, ⌘⌥) + "Reset to Default" link |
| Home tab | 22px title, GlassCard instruction, "Refer Friends" placeholder | 28px/800-weight title, inline keycap instruction, "Support Us" with GitHub star button |
| History tab | White cards, no separator | Chat bubbles with asymmetric radii (4px top-left), vertical sidebar separator |
| Dictionary tab | Emoji 👤 avatar, orange pill "+" button | Monogram circle avatar, native SecondaryButton for "+" |
| Configs tab | Left-aligned labels, GlassCard wrapper | Right-aligned labels, SectionFrame cards, permission status with ✓/✗ color |
| Dark mode | Followed system (broken visuals with hardcoded light colors) | Forced Aqua light mode via `NSApp.setAppearance_()` |

### Files Modified in This Session

| File | Changes |
|------|---------|
| `talky/ui.py` | Complete rewrite: `NATIVE_STYLESHEET`, segmented tab bar, radio button hotkey group, keycap badges, chat bubble history, monogram avatars, "Support Us" card with GitHub link, `_clear_layout` recursive fix, `AlignTop` on dictionary grid |
| `main.py` | Added `NSApp.setAppearance_(NSAppearanceNameAqua)` to force light mode |

### Specific Issues Resolved

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| History entries overlap when switching dates | `_clear_layout()` only removed widget items, skipped child layouts (`addLayout` rows) | Made `_clear_layout()` recursive: also clears nested `item.layout()` |
| Dictionary word spacing auto-stretches, no scroll | `QGridLayout` without `AlignTop` distributes rows evenly across full height | Added `setAlignment(Qt.AlignmentFlag.AlignTop)` to grid layout |
| Dark mode breaks UI | Stylesheet uses hardcoded light colors but window chrome follows system | `NSApp.setAppearance_("NSAppearanceNameAqua")` forces Aqua globally |

### Key Design Details

- **Accent color:** `#ED4A20` (preserved throughout)
- **Keycap badge:** Gradient background (#FCFCFC → #ECECEC), differentiated border widths (top 1px lighter, bottom 2px darker), SF Mono 12px semibold
- **Segmented control:** Gray container (6px radius), white selected tab with orange text
- **Section frames:** White background, 10px radius, 1px border at 8% opacity
- **Chat bubbles:** `#F2F2F7` background, 14px radius with 4px top-left for Messages.app feel
- **Permission status:** Green ✓ `#34C759` / Red ✗ `#FF3B30`
- **GitHub link:** `https://github.com/shintemy/talky`

---

## Session 1 — DMG Build Pipeline (2026-03-19)

### Build Pipeline

`scripts/build_unsigned_dmg.sh` — one-command PyInstaller → `.app` → `.dmg`, including:

- MLX metallib bundling (`--add-data mlx/lib`)
- mlx_whisper assets bundling (`--add-data mlx_whisper/assets` — mel_filters.npz, tiktoken files)
- Tray icon bundling (`--add-data assets/tray_icon*.png`)
- Talky logo bundling (`--add-data assets/talky-logo.png`) for Dashboard Home tab
- AVFoundation hidden-import for PyInstaller
- `PYINSTALLER_CONFIG_DIR` redirect, specpath/icon absolute paths
- `Info.plist` post-injection:
  - `CFBundleIdentifier = com.talky.app`
  - `NSMicrophoneUsageDescription`
  - `NSInputMonitoringUsageDescription`
  - `NSSupportsAutomaticTermination = false`
  - `NSSupportsSuddenTermination = false`
- Entitlements creation (`com.apple.security.device.audio-input`)
- Ad-hoc re-signing with `codesign --force --deep --sign - --identifier com.talky.app --entitlements ...`
- Signature verification (identifier match check)

### Issues Resolved in Session 1

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Mic permission prompt never appears | PyInstaller ad-hoc signs before plist injection; Identifier mismatch (`Talky` vs `com.talky.app`); no audio-input entitlement; `Info.plist=not bound` | Build script: create entitlements.plist + re-sign after plist injection with correct `--identifier` |
| Whisper model path not found (`/local_whisper_model`) | `.app` launches with CWD=`/`; relative `./local_whisper_model` resolves to root | `_resolve_model_reference()` tries `~/.talky/` first, then CWD; symlink created at `~/.talky/local_whisper_model` |
| `ffmpeg` not found | `.app` PATH lacks `/opt/homebrew/bin` | `transcribe()` reads WAV via soundfile → numpy array, passes directly to mlx_whisper (bypasses ffmpeg) |
| `mel_filters.npz` load failure | `mlx_whisper/assets/` not bundled by PyInstaller | Build script adds `--add-data` for mlx_whisper assets directory |
| Settings panel auto-shows on launch | macOS Dock activation event triggers tray activated signal; stale signal file from previous run | 1.5s startup guard on tray click handler; clean stale signal file on watcher start |
| Quit → auto-restart loop | macOS state restoration relaunches Dock apps | `disableRelaunchOnLogin()` in code; `NSSupportsAutomaticTermination=false` in plist; `os._exit(0)` fallback 500ms after `QApplication.quit()` |

### App Functionality Changes (Session 1, all in worktree)

| File | Change |
|------|--------|
| `main.py` | Single-instance lock; deferred mic permission request; `disableRelaunchOnLogin()` to prevent macOS auto-relaunch |
| `talky/asr_service.py` | `_resolve_model_reference()` checks `~/.talky/` before CWD for relative paths; `transcribe()` reads WAV as numpy via soundfile (no ffmpeg dependency) |
| `talky/controller.py` | Error logging to `~/.talky/logs/error.log`; error notifications include log path; hotkey fallback fn→right_option; "audio too quiet" includes device name |
| `talky/hotkey.py` | `start()` returns `bool`; `threading.Event` for event tap confirmation; `on_error` callback; `kCGEventTapOptionListenOnly` |
| `talky/permissions.py` | No false-positive on mic when AVFoundation unavailable; explicit "status unavailable" |
| `talky/recorder.py` | `_select_input_device_index()` prefers built-in mic; `active_input_device_label` property |
| `requirements.txt` | Added `pyobjc-framework-AVFoundation` |
| `.gitignore` | Added `release/`, `*.spec`, `.worktrees/` |
| `README.md` / `README.zh.md` | Added DMG build section |

### Dashboard Implementation (Session 1)

- Renamed "Settings" to **Dashboard**
- 4-tab layout: **Home** | **History** | **Dictionary** | **Configs**
- Configs tab: auto-save on close (no Save button)
- **Cmd+W** to close Dashboard
- Logo Retina fix: `setDevicePixelRatio` for crisp display
- History path: `~/.talky/history/` (persistent across DMG runs)
- `talky/version_checker.py`: update detection from `~/.talky/update_info.json`

### New Files (across both sessions)

| File | Purpose |
|------|---------|
| `scripts/build_unsigned_dmg.sh` | One-command unsigned DMG builder with entitlements and re-signing |
| `assets/tray_icon.png` | Menu Bar icon @1x (22x22, black on transparent) |
| `assets/tray_icon@2x.png` | Menu Bar icon @2x (44x44, black on transparent) |
| `docs/DMG_README.md` | Standalone user-facing install and usage guide for DMG distribution |
| `docs/DMG_INTERNAL_TESTING.md` | Internal testing flow and acceptance checklist |
| `docs/DMG_SESSION_HANDOFF.md` | This file |
| `tests/test_asr_service.py` | Tests for model path resolution and missing-path error |

### External Setup (not in repo)

- `~/.talky/local_whisper_model` → symlink to project's `local_whisper_model/` (whisper-large-v3-mlx, ~3GB)

### Test Status

- `2 passed` in `tests/test_asr_service.py` (model path resolution tests)
- Full suite not re-run in session 2; session 1 reported `38 passed, 2 skipped`

---

## Next Steps (for next session)

### ~~P1: DMG size reduction~~ ✓ Done (Session 3)

Completed: 264 MB → 108 MB (-59%). See Session 3 above.

### P2: Code signing & notarization

- Developer ID certificate
- `codesign` with real identity
- `xcrun notarytool` submission
- Removes Gatekeeper warnings for end users

### P3: Whisper model bundling / auto-download

- Consider HuggingFace auto-download fallback if `~/.talky/local_whisper_model` is missing
- Or bundle a smaller model inside the `.app`

## Remaining Known Issues (lower priority)

- **fn hotkey unreliable**: depends on macOS version and keyboard config; auto-falls back to Right Option with notification. Suggested: add hotkey self-test in settings UI.
- **Accessibility permission cache**: installing new `.app` over old sometimes keeps stale "not granted" state; user must manually remove and re-add in System Settings.
- **Documents folder access prompt**: appears once due to symlinked Whisper model in `~/Documents/`. Harmless; click Allow.
- **Whisper model not bundled**: model must exist at `~/.talky/local_whisper_model` (symlink or copy).

---

## Files Changed (relative to main branch)

```
Modified:
  .gitignore
  README.md
  README.zh.md
  main.py
  requirements.txt
  talky/asr_service.py
  talky/controller.py
  talky/hotkey.py
  talky/permissions.py
  talky/recorder.py
  talky/ui.py
  tests/test_main.py
  tests/test_permissions.py
  tests/test_recorder.py

New:
  assets/tray_icon.png
  assets/tray_icon@2x.png
  docs/DMG_INTERNAL_TESTING.md
  docs/DMG_README.md
  docs/DMG_SESSION_HANDOFF.md
  scripts/build_unsigned_dmg.sh
  tests/test_asr_service.py
```
