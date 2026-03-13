#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "==> Talky one-click start"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is not installed. Please install Python 3 first."
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "==> Creating virtual environment..."
  python3 -m venv .venv
fi

source ".venv/bin/activate"

echo "==> Installing dependencies..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt >/dev/null

if [[ ! -d "local_whisper_model" ]]; then
  echo "==> local_whisper_model not found, downloading..."
  python download_model.py
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "Error: ollama command not found."
  echo "Please install Ollama first: https://ollama.com/download"
  exit 1
fi

mkdir -p ".logs"

if ! pgrep -x "ollama" >/dev/null 2>&1; then
  echo "==> Starting Ollama service..."
  nohup ollama serve >".logs/ollama.log" 2>&1 &
  sleep 2
fi

MODEL_NAME="$(
python - <<'PY'
import json
import subprocess
from pathlib import Path

config_path = Path.home() / ".talky" / "settings.json"
data = {}
if config_path.exists():
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}

configured = str(data.get("ollama_model", "")).strip()

installed: list[str] = []
try:
    raw = subprocess.check_output(["ollama", "list"], text=True)
    for line in raw.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        name = line.split()[0].strip()
        if name:
            installed.append(name)
except Exception:
    installed = []

selected = ""
if configured and configured in installed:
    selected = configured
elif installed:
    selected = installed[0]
    data["ollama_model"] = selected
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

print(selected)
PY
)"

if [[ -z "$MODEL_NAME" ]]; then
  echo "Error: no Ollama model found."
  echo "Please pull any model first, for example:"
  echo "  ollama pull <your-model>"
  echo "Then re-run start_talky.command."
  exit 1
fi

echo "==> Using Ollama model: $MODEL_NAME"

echo "==> Launching Talky..."
exec python main.py
