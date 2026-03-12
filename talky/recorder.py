from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf


class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        if self._stream is not None:
            return
        self._chunks.clear()

        def _callback(indata: np.ndarray, frames: int, time_info: dict, status) -> None:
            del frames, time_info
            if status:
                # Keep the stream alive even if occasional status is present.
                pass
            self._chunks.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=_callback,
        )
        self._stream.start()

    def stop_and_dump_wav(self) -> Path:
        if self._stream is None:
            raise RuntimeError("Recorder is not running.")

        self._stream.stop()
        self._stream.close()
        self._stream = None

        if not self._chunks:
            raise RuntimeError("No audio captured.")

        audio = np.concatenate(self._chunks, axis=0)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        path = Path(tmp.name)
        tmp.close()
        sf.write(path, audio, self.sample_rate)
        self._chunks.clear()
        return path
