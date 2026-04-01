from __future__ import annotations

from talky.model_name_guard import apple_script_escape, build_pull_command, is_safe_ollama_model_name


def test_model_name_guard_accepts_common_model_names() -> None:
    assert is_safe_ollama_model_name("qwen3.5:9b")
    assert is_safe_ollama_model_name("deepseek-r1:8b")
    assert is_safe_ollama_model_name("org/model-name:latest")


def test_model_name_guard_rejects_shell_metacharacters() -> None:
    assert not is_safe_ollama_model_name("qwen3.5:9b; rm -rf /")
    assert not is_safe_ollama_model_name("`whoami`")
    assert not is_safe_ollama_model_name('abc"def')


def test_build_pull_command_and_applescript_escape() -> None:
    cmd = build_pull_command("qwen3.5:9b")
    assert cmd == "ollama pull qwen3.5:9b"
    assert apple_script_escape('echo "x" \\ y') == 'echo \\"x\\" \\\\ y'
