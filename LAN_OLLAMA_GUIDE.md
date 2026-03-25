# LAN Ollama Guide

Use this guide when `Mac mini` hosts Ollama models and `MacBook` runs Talky.

> **Using the DMG build?** Configure **Dashboard → Configs** instead — see **[DMG: LAN Ollama](docs/DMG_LAN_OLLAMA.md)**. The steps below assume the source tree + `start_talky.command`.

## Step 1 (Mac mini): prepare Ollama service and model

```bash
ollama --version
ollama ls
pkill ollama
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

Open another terminal on Mac mini to verify listener:

```bash
lsof -nP -iTCP:11434 -sTCP:LISTEN
```

Expected: `*:11434` or `0.0.0.0:11434`

## Step 2 (Mac mini): get LAN IP

```bash
ipconfig getifaddr en1
```

If `en1` has no output, try:

```bash
ipconfig getifaddr en0
```

## Step 3 (MacBook): verify connectivity and remote API

```bash
nc -vz <LAN_IP> 11434
curl http://<LAN_IP>:11434/api/tags
```

Expected:
- `nc` shows `succeeded`
- `curl` returns model list (for example `qwen3.5:4b`)

## Step 4 (MacBook): one-line switch to LAN mode + auto-restart

```bash
cd /path/to/talky
./start_talky.command --remote "http://<LAN_IP>:11434" --model "qwen3.5:4b" --restart
```

## Step 5: success signals

You should see these logs:
- `mode: remote`
- `Using Ollama model: qwen3.5:4b`
- `ASR elapsed`, `LLM elapsed`, `Final text`

## Quick troubleshooting

- `bind: address already in use`
  - Port `11434` is occupied. Run `pkill ollama` and retry Step 1.
- `nc` cannot connect
  - Check Mac mini firewall and router client isolation settings.
- `curl /api/tags` works but Talky says model not found
  - Make sure `--model` exactly matches `ollama ls`.
