# Talky DMG: LAN Ollama (Ollama on Mac mini, Talky on MacBook)

**Scenario:** Run **Ollama** on a **Mac mini** (LLM host) and **Talky** from the **DMG** on a **MacBook**. **Whisper ASR** runs **on the MacBook**; only **LLM cleanup** calls go to the Mac mini.

> **vs Cloud mode**  
> - **This guide (Local + remote Ollama):** ASR on **MacBook**, LLM on **Mac mini**.  
> - **Cloud mode:** Audio is uploaded to **Talky Cloud**; ASR + LLM run on the server. Requires `talky-server` + API key — see `talky-server/README.md`.

---

## Prerequisites

| Item | Notes |
|------|------|
| Two Macs | Same LAN (same Wi‑Fi or same subnet) |
| MacBook | Apple Silicon; Talky installed from DMG (e.g. `Talky-*-unsigned.dmg`) |
| Mac mini | Ollama installed; model pulled with `ollama pull` |
| Whisper | **Still on MacBook:** complete model download or path in Talky on first use |

---

## Step 1: Expose Ollama on the Mac mini

1. Optionally stop old processes:

   ```bash
   pkill ollama
   ```

2. **Listen on all interfaces** (default may be `127.0.0.1` only):

   ```bash
   OLLAMA_HOST=0.0.0.0:11434 ollama serve
   ```

3. Verify listen address:

   ```bash
   lsof -nP -iTCP:11434 -sTCP:LISTEN
   ```

   Expect `*:11434` or `0.0.0.0:11434`.

4. Confirm models:

   ```bash
   ollama list
   ```

   Copy the **exact** model name (e.g. `qwen3.5:9b`) for Talky.

5. **Firewall:** allow inbound connections to Ollama, or disable temporarily for testing.

---

## Step 2: Mac mini LAN IP

On **Mac mini**:

```bash
ipconfig getifaddr en0
```

Try `en1` if empty. Or check **System Settings → Network**.

Replace **`192.168.31.210`** below with your real IP.

---

## Step 3: Test from MacBook

On **MacBook**:

```bash
nc -vz 192.168.31.210 11434
curl -sS http://192.168.31.210:11434/api/tags
```

`curl` should return JSON with `models`. If not, fix IP, firewall, or `OLLAMA_HOST` first.

---

## Step 4: Configure Talky (DMG)

1. Launch **Talky** from Applications.

2. Open **Dashboard** (shortcut: **Control + Option + Command**, or menu bar icon).

3. Open the **Configs** tab.

4. Set **Processing Mode** to **Local (Free)** (not Cloud).

5. Fill in:

   | Field | Value |
   |------|--------|
   | **Ollama Host** | `http://192.168.31.210:11434` (`http://` + Mac mini IP + `:11434`) |
   | **Ollama Model** | **Exact** name from `ollama list` on Mac mini |
   | **Whisper Model** | Local path or Hugging Face repo ID (ASR stays on MacBook) |

6. Close the Dashboard window — **Configs auto-save** to `~/.talky/settings.json`.

7. If Whisper is not set up yet, the **model setup** dialog appears on first **fn** press; follow prompts.

---

## Step 5: Usage

1. Focus a text field in any app.  
2. **Hold fn** (or your configured hotkey) and speak.  
3. **Release** and wait.  
4. Text should paste into the frontmost app, or a **floating copy panel** if no focus.

**Pipeline:** Whisper on MacBook → text to Mac mini Ollama → cleaned text back → paste.

---

## Troubleshooting

### LLM errors / timeouts

- Mac mini: `ollama serve` running with `OLLAMA_HOST=0.0.0.0:11434`.  
- **Ollama Model** matches `ollama list`.  
- From MacBook: `curl http://<IP>:11434/api/tags`.

### ASR / Whisper errors

- These are **local to MacBook**; check **Whisper Model** path and first-time download.

### Relation to `LAN_OLLAMA_GUIDE.md` / `start_talky.command`

- **From source:** you can use `start_talky.command --remote ...` (see that guide).  
- **DMG users** configure **Dashboard → Configs** instead; behavior is equivalent (Local + remote Ollama).

---

## See also

- Command-line LAN guide (`start_talky.command`): [LAN_OLLAMA_GUIDE.md](../LAN_OLLAMA_GUIDE.md)  
- Talky Cloud server: [talky-server/README.md](../talky-server/README.md)  
- Prebuilt DMG: [GitHub Releases](https://github.com/shintemy/talky/releases) (internal builds are *unsigned*; allow in Privacy & Security on first open)
