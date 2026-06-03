from __future__ import annotations

import json
from pathlib import Path


def obsidian_config_path() -> Path:
    """Path to Obsidian's vault registry on macOS."""
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "obsidian"
        / "obsidian.json"
    )


def detect_default_vault(config_path: Path | None = None) -> str | None:
    """Return the path of the current/most-recent Obsidian vault, or None.

    Selection: prefer the vault with open == True; otherwise the one with the
    largest ts. Reads only Application Support (no TCC-protected access).
    Tolerant: missing file / bad JSON / empty vaults / entries without a path
    all yield None (or are skipped).
    """
    path = config_path or obsidian_config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    vaults = data.get("vaults")
    if not isinstance(vaults, dict) or not vaults:
        return None
    best_key: tuple[int, int] | None = None
    best_path: str | None = None
    for entry in vaults.values():
        if not isinstance(entry, dict):
            continue
        vault_path = entry.get("path")
        if not vault_path:
            continue
        key = (1 if entry.get("open") else 0, int(entry.get("ts") or 0))
        if best_key is None or key > best_key:
            best_key = key
            best_path = str(vault_path)
    return best_path
