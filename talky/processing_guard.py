from __future__ import annotations


def should_timeout_processing(elapsed_seconds: float, timeout_seconds: float) -> bool:
    return elapsed_seconds >= timeout_seconds


def estimate_asr_timeout_seconds(
    audio_duration_seconds: float,
    *,
    min_timeout_seconds: float = 35.0,
    max_timeout_seconds: float = 180.0,
) -> float:
    duration = max(0.0, audio_duration_seconds)
    # Large models can take significantly longer than audio duration on some Macs.
    estimated = duration * 2.0 + 15.0
    return min(max_timeout_seconds, max(min_timeout_seconds, estimated))


def estimate_processing_timeout_seconds(
    audio_duration_seconds: float,
    *,
    llm_timeout_seconds: float = 25.0,
    min_timeout_seconds: float = 45.0,
    max_timeout_seconds: float = 240.0,
) -> float:
    asr_timeout = estimate_asr_timeout_seconds(audio_duration_seconds)
    estimated = asr_timeout + llm_timeout_seconds + 10.0
    return min(max_timeout_seconds, max(min_timeout_seconds, estimated))
