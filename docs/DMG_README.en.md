# Talky — DMG Install Guide

Talky is a local voice-input assistant built for macOS Apple Silicon.
Hold a hotkey to speak, release to automatically transcribe, polish, and paste text into the active app.

## System Requirements

- **macOS 13 (Ventura)** or later
- **Apple Silicon** chip (M1 / M2 / M3 / M4 series)
- At least **16 GB** RAM (recommended for Whisper Large + Ollama 9B model)
- At least **10 GB** free disk space

## Before You Install

### 1. Install Ollama

Talky uses Ollama to run a local LLM for polishing speech recognition results.

1. Go to [ollama.com/download](https://ollama.com/download) to download and install.
2. Once installed, pull the default model:

```bash
ollama pull qwen3.5:9b
```

Verify Ollama is running:

```bash
ollama list
```

You should see `qwen3.5:9b` or whichever model you chose.

### 2. Prepare the Whisper Speech Recognition Model

Talky uses MLX Whisper for on-device speech recognition. Two ways to get the model:

**Option A: Automatic download from HuggingFace (recommended, requires internet)**

After installing Talky, go to Dashboard → Configs and enter this in the Whisper Model field:

```
mlx-community/whisper-large-v3-mlx
```

The model (~3 GB) will be downloaded automatically on your first recording and cached locally.

**Option B: Manually place model files**

If you already have the model files, place them at:

```
~/.talky/local_whisper_model/
├── config.json
└── weights.npz
```

In Dashboard → Configs, keep the default Whisper Model value `./local_whisper_model`.

## Install Talky

1. Double-click the `.dmg` file to open it.
2. Drag `Talky.app` into the `Applications` folder.
3. Open `Talky` from Applications.
4. On first launch, macOS will warn "cannot verify the developer" (expected for unsigned apps):
   - Open **System Settings → Privacy & Security**
   - Find the Talky prompt and click **Open Anyway**
5. Grant the following permissions when prompted:
   - **Microphone** — required for voice recording
   - **Accessibility** — required for global hotkeys and auto-paste
   - **Input Monitoring** — required for global hotkey listening

## Daily Usage

### Menu Bar Icon

After launch, a Talky bubble icon appears in the top-right Menu Bar. Click it to see the menu:

- **Dashboard** — open the main panel (Home / History / Dictionary / Configs)
- **Show Last Error** — view the most recent error details
- **Quit** — exit Talky

### Voice Input

1. Hold **fn** (Globe key) to start recording
2. Speak into your microphone
3. Release fn → automatic processing: speech recognition → LLM polish → paste at cursor

If no pasteable target window is available, a floating panel will appear with the result for manual copying.

### Keyboard Shortcuts

| Shortcut | Function |
|----------|----------|
| Hold **fn** | Record (press to start, release to stop) |
| **Control + Option + Command** | Open Dashboard |
| **Command + W** | Close Dashboard (when focused) |

### Dashboard

Open via the Menu Bar menu or keyboard shortcut. Contains four tabs:

- **Home** — Logo, usage guide, version update notice
- **History** — View transcription records by date (stored in `~/.talky/history/`)
- **Dictionary** — Custom word management: add, edit, delete entries (supports `person:Name` format)
- **Configs** — Settings, auto-saved when the panel is closed

Configs options:

- **Record Hotkey** — recording hotkey (fn / Right Option / custom combo)
- **Whisper Model** — model path or HuggingFace repo ID
- **ASR Language** — speech recognition language (default `zh`)
- **Ollama Host** — Ollama server address (default `http://127.0.0.1:11434`)
- **Ollama Model** — LLM model name (default `qwen3.5:9b`)
- **Auto Paste Delay** — paste delay in milliseconds

## Troubleshooting

### Microphone permission prompt doesn't appear

1. Open Terminal and run:
   ```bash
   tccutil reset Microphone
   ```
2. Reopen Talky — the authorization prompt should appear.

### "audio too quiet" after recording

- Check that the correct input device is selected in System Settings (built-in mic vs external).
- Check System Settings → Sound → Input volume.

### Ollama-related error after recording

- Confirm Ollama is running: `ollama list`
- Confirm the model is pulled: `ollama pull qwen3.5:9b`
- If using a remote Ollama, update the Ollama Host address in Dashboard → Configs.

### fn key not responding

The fn (Globe) key can be unreliable on some macOS configurations. Talky will automatically fall back to the Right Option key with a notification. You can also manually switch the hotkey in Dashboard → Configs.

### "Accessibility permission missing"

Open **System Settings → Privacy & Security → Accessibility**, find Talky and enable it. If it's already listed but not working, remove it and re-add.

## Uninstall

1. Delete `Talky.app` from the Applications folder.
2. Clean up config files (optional):
   ```bash
   rm -rf ~/.talky
   ```
