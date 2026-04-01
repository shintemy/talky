from __future__ import annotations

import re

_MODEL_NAME_SAFE_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")


def is_safe_ollama_model_name(name: str) -> bool:
    value = (name or "").strip()
    return bool(_MODEL_NAME_SAFE_RE.fullmatch(value))


def build_pull_command(model_name: str) -> str:
    value = (model_name or "").strip()
    return f"ollama pull {value}"


def apple_script_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
