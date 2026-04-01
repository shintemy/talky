from __future__ import annotations

from talky.warmup_policy import should_warm_up_asr


def test_asr_warmup_policy_defaults_to_disabled(monkeypatch) -> None:
    monkeypatch.delenv("TALKY_ASR_WARMUP", raising=False)
    assert not should_warm_up_asr()


def test_asr_warmup_policy_accepts_truthy_values(monkeypatch) -> None:
    for value in ("1", "true", "yes", "on", "TRUE"):
        monkeypatch.setenv("TALKY_ASR_WARMUP", value)
        assert should_warm_up_asr()
