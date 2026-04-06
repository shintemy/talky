# Talky

![Talky Banner](assets/github-banner.png)

**Speak it. Ship it.** The first fully-local voice engine for vibe coding.  
On-device Whisper + LLM — hold to talk, release to paste. No cloud. No compromise.

**Language:** English | [中文](README.zh.md)

## Download

**[Download Talky DMG (latest release)](https://github.com/shintemy/talky/releases/latest)**

> macOS Apple Silicon · Unsigned / not notarized — see install steps below.

## How It Works

1. **Hold** the Fn key to start recording
2. **Speak** naturally
3. **Release** — Talky transcribes your speech (Whisper) and refines it with a local LLM (Ollama)
4. **Text is pasted** into the active app automatically

If no input field is focused, a floating copy panel appears so you can manually paste.

## Install

1. Download the `.dmg` from [Releases](https://github.com/shintemy/talky/releases/latest)
2. Open the DMG, drag **Talky** to **Applications**
3. First launch: macOS will block the app — go to **System Settings → Privacy & Security** and click **Open Anyway**
4. Grant **Microphone** and **Accessibility** permissions when prompted
5. The setup wizard will guide you through installing [Ollama](https://ollama.com/download), an AI model, and a speech model

## Features

### Vibe Coding Mode

Switch to **Vibecoding** in Dashboard → Configs to turn spoken ideas in any language into concise English prompts — ready to paste into Cursor, Claude, or any AI coding agent.

<img src="assets/vibecoding-mode.png" alt="Vibecoding mode in Talky Dashboard" width="520">

- **100% Local** — ASR + LLM run on your Mac, nothing is uploaded
- **Hold-to-Talk** — simple press-and-hold interaction, no wake words
- **Smart Paste** — auto-pastes into the active text field; fallback copy panel when no target
- **Custom Prompt** — edit the LLM system prompt to match your writing style
- **Dictionary** — add custom terms for better recognition of names, jargon, etc.
- **Multi-Mode** — Local / Remote Ollama / Cloud server
- **Daily History** — all transcriptions archived locally

## Requirements

- macOS (Apple Silicon: M1 / M2 / M3 / M4)
- [Ollama](https://ollama.com/download) installed
- ~10 GB free disk space (for AI + speech models)

## Troubleshooting

**App won't open?**  
System Settings → Privacy & Security → scroll down → click "Open Anyway".

**No text output?**  
Make sure Ollama is running (`ollama serve` in Terminal).

**Whisper model issues?**  
Delete `~/.cache/huggingface/hub/` and re-download through the app.

## License

Private project. All rights reserved.
