from __future__ import annotations


def is_accessibility_trusted(prompt: bool = False) -> bool:
    try:
        from ApplicationServices import (
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )

        return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: prompt}))
    except Exception:
        return False


def check_ollama_reachable() -> tuple[bool, str]:
    try:
        import ollama

        ollama.list()
        return True, ""
    except Exception as exc:
        return False, f"Ollama service unavailable: {exc}"
