from __future__ import annotations

from pathlib import Path

import mlx_whisper
import numpy as np
import soundfile as sf


class MlxWhisperASR:
    def __init__(self, model_name: str, language: str = "zh") -> None:
        self.model_name = model_name
        self.language = language

    def transcribe(self, audio_path: Path, initial_prompt: str) -> str:
        model_ref = self._resolve_model_reference()
        audio, _sr = sf.read(audio_path, dtype="float32")
        if audio.ndim > 1:
            audio = audio[:, 0]
        kwargs = {"initial_prompt": initial_prompt, "language": self.language}
        try:
            result = mlx_whisper.transcribe(
                audio,
                path_or_hf_repo=model_ref,
                **kwargs,
            )
        except TypeError:
            result = mlx_whisper.transcribe(audio, model_ref, **kwargs)
        text = result.get("text", "") if isinstance(result, dict) else str(result)
        return text.strip()

    def warm_up(self) -> None:
        # Use in-memory silent waveform to avoid depending on ffmpeg for warm-up.
        silent = np.zeros(8000, dtype=np.float32)  # 0.5s @ 16k
        model_ref = self._resolve_model_reference()
        kwargs = {"initial_prompt": "", "language": self.language}
        try:
            mlx_whisper.transcribe(
                silent,
                path_or_hf_repo=model_ref,
                **kwargs,
            )
        except TypeError:
            mlx_whisper.transcribe(silent, model_ref, **kwargs)

    def _resolve_model_reference(self) -> str:
        raw_value = (self.model_name or "").strip() or "./local_whisper_model"
        if not raw_value.startswith(("/", "./", "../", "~")):
            return raw_value

        resolved = Path(raw_value).expanduser()
        if not resolved.is_absolute():
            candidates = [
                (Path.home() / ".talky" / resolved).resolve(),
                (Path.cwd() / resolved).resolve(),
            ]
        else:
            candidates = [resolved]

        for path in candidates:
            if path.exists():
                return str(path)

        searched = "\n  ".join(str(p) for p in candidates)
        raise FileNotFoundError(
            f"Whisper model path not found. Searched:\n  {searched}\n"
            "Set 'Whisper Model' to a valid absolute path or Hugging Face repo id "
            "(e.g. mlx-community/whisper-large-v3-mlx)."
        )
