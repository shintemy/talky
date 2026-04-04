from __future__ import annotations

import os


def should_warm_up_asr() -> bool:
    """
    ASR warm-up runs by default so the first transcription is fast.

    Set TALKY_ASR_WARMUP=0 to disable if Metal driver issues occur at startup.
    """
    value = os.environ.get("TALKY_ASR_WARMUP", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}
