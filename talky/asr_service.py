from __future__ import annotations

from pathlib import Path

import mlx_whisper
import numpy as np


class MlxWhisperASR:
    def __init__(self, model_name: str, language: str = "zh") -> None:
        self.model_name = model_name
        self.language = language

    def transcribe(self, audio_path: Path, initial_prompt: str) -> str:
        kwargs = {"initial_prompt": initial_prompt, "language": self.language}
        try:
            result = mlx_whisper.transcribe(
                str(audio_path),
                path_or_hf_repo=self.model_name,
                **kwargs,
            )
        except TypeError:
            result = mlx_whisper.transcribe(str(audio_path), self.model_name, **kwargs)
        text = result.get("text", "") if isinstance(result, dict) else str(result)
        return text.strip()

    def warm_up(self) -> None:
        # Use in-memory silent waveform to avoid depending on ffmpeg for warm-up.
        silent = np.zeros(8000, dtype=np.float32)  # 0.5s @ 16k
        kwargs = {"initial_prompt": "", "language": self.language}
        try:
            mlx_whisper.transcribe(
                silent,
                path_or_hf_repo=self.model_name,
                **kwargs,
            )
        except TypeError:
            mlx_whisper.transcribe(silent, self.model_name, **kwargs)
