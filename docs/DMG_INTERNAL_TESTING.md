# Talky Unsigned DMG Internal Testing

This guide is for phase 1 delivery: shipping an unsigned, non-notarized DMG for internal testers.

## 1. Prerequisites

- macOS Apple Silicon machine
- Ollama installed and running (`ollama serve`)
- Whisper model available at `~/.talky/local_whisper_model` (symlink or real directory)

## 2. Build unsigned DMG

From worktree root:

```bash
./scripts/build_unsigned_dmg.sh
```

Optional custom version string:

```bash
./scripts/build_unsigned_dmg.sh "0.1.0-internal.19"
```

Output path:

- `release/Talky-<version>-unsigned.dmg`

The build script automatically:
- Bundles MLX metallib and mlx_whisper assets (mel filters, tokenizers)
- Injects `NSMicrophoneUsageDescription`, `NSInputMonitoringUsageDescription` into Info.plist
- Creates `entitlements.plist` with `com.apple.security.device.audio-input`
- Re-signs the app (ad-hoc) with correct `CFBundleIdentifier = com.talky.app`
- Verifies the code signature and identifier match

## 3. First-time install

1. If upgrading from a previous build, first reset TCC to clear stale permission state:
   ```bash
   tccutil reset Microphone
   ```
2. Open DMG.
3. Drag `Talky.app` into `Applications` (overwrite if exists).
4. Open `Applications/Talky.app`.
5. If Gatekeeper warns (expected for unsigned app):
   - Open `System Settings -> Privacy & Security`.
   - Click `Open Anyway` for Talky.
6. If prompted for Documents folder access: click **Allow** (needed for symlinked Whisper model).
7. Grant **Microphone** permission when the system prompt appears.
8. Grant **Accessibility** and **Input Monitoring** in System Settings for hotkey support.

## 4. Usage

- **Menu Bar icon**: bubble chat icon in the top-right menu bar area.
- **Hold fn** to record, release to process (ASR → LLM → paste).
- **Control + Option + Command**: open Dashboard.
- **Click Menu Bar icon** → context menu (Dashboard / Show Last Error / Quit).
- **Dock icon**: visible, clicking it while app is running has no effect.

### Dashboard (4 tabs)

- **Home** — Logo, usage guide, Refer friends placeholder, version update banner (if new version detected).
- **History** — Text output records by date (from `~/.talky/history/`), click date to view entries.
- **Dictionary** — Custom words (3 per row), hover to show Edit/Delete, "New word" to add.
- **Configs** — Hotkey, Whisper/Ollama settings, UI language, paste delay, permissions. Auto-save on close (no Save button).
- **Cmd+W** — Close Dashboard.

## 5. Acceptance checklist (phase 1)

A build is accepted only when all checks pass:

- [x] DMG is created successfully from `./scripts/build_unsigned_dmg.sh`.
- [x] `Talky.app` installs from DMG by drag-and-drop.
- [x] App launches from `Applications` without terminal commands.
- [x] Microphone authorization prompt appears on first launch.
- [x] First recording round trip works (record → ASR → LLM → paste).
- [x] Dashboard does NOT auto-show on launch.
- [x] Quit from tray menu exits cleanly (no auto-restart).
- [x] Custom Menu Bar icon displays correctly.
- [x] Required permissions can be granted and rechecked in UI.
- [ ] Test notes include macOS version, chip type, and any failure logs.

## 6. User-facing documentation

- `docs/DMG_README.md` — standalone install and usage guide for DMG users (no source-code knowledge needed)

## 7. Out of scope in phase 1

- Code signing with Developer ID
- Notarization
- Gatekeeper warning removal
- Bundling Whisper model inside the .app
- ~~DMG size reduction~~ (done: 264 MB → 108 MB via `--exclude-module torch llvmlite scipy numba`)

These are phase 2 tasks once internal testing metrics are stable.
