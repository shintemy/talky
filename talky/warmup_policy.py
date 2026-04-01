from __future__ import annotations

import os


def should_warm_up_asr() -> bool:
    """
    ASR warm-up is opt-in.

    Some macOS + Metal driver combinations are unstable during background warm-up.
    Keep startup stable by default and allow manual enabling via env flag.
    """
    value = os.environ.get("TALKY_ASR_WARMUP", "0").strip().lower()
    return value in {"1", "true", "yes", "on"}
