import json
from pathlib import Path

from talky.obsidian_vault import detect_default_vault, obsidian_config_path


def _write_registry(path: Path, vaults: dict) -> None:
    path.write_text(json.dumps({"vaults": vaults}), encoding="utf-8")


def test_config_path_is_macos_application_support():
    p = obsidian_config_path()
    assert p == Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json"


def test_detect_single_open_vault(tmp_path):
    cfg = tmp_path / "obsidian.json"
    _write_registry(cfg, {"a": {"path": "/V/MyVault", "ts": 111, "open": True}})
    assert detect_default_vault(cfg) == "/V/MyVault"


def test_detect_prefers_open_over_newer_ts(tmp_path):
    cfg = tmp_path / "obsidian.json"
    _write_registry(cfg, {
        "a": {"path": "/V/Open", "ts": 100, "open": True},
        "b": {"path": "/V/NewerButClosed", "ts": 999, "open": False},
    })
    assert detect_default_vault(cfg) == "/V/Open"


def test_detect_falls_back_to_newest_ts_when_none_open(tmp_path):
    cfg = tmp_path / "obsidian.json"
    _write_registry(cfg, {
        "a": {"path": "/V/Older", "ts": 100},
        "b": {"path": "/V/Newer", "ts": 200},
    })
    assert detect_default_vault(cfg) == "/V/Newer"


def test_detect_missing_file(tmp_path):
    assert detect_default_vault(tmp_path / "nope.json") is None


def test_detect_malformed_json(tmp_path):
    cfg = tmp_path / "obsidian.json"
    cfg.write_text("{ not json", encoding="utf-8")
    assert detect_default_vault(cfg) is None


def test_detect_empty_vaults(tmp_path):
    cfg = tmp_path / "obsidian.json"
    _write_registry(cfg, {})
    assert detect_default_vault(cfg) is None


def test_detect_skips_entries_without_path(tmp_path):
    cfg = tmp_path / "obsidian.json"
    _write_registry(cfg, {
        "a": {"ts": 999, "open": True},          # no path -> skipped
        "b": {"path": "/V/Good", "ts": 1},
    })
    assert detect_default_vault(cfg) == "/V/Good"
