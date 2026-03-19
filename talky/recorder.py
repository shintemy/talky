from __future__ import annotations

import tempfile
import time
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
        self._active_sample_rate = float(sample_rate)
        self._last_duration_s = 0.0
        self._last_rms = 0.0
        self._active_input_device: int | None = None
        self._active_input_device_label = "unknown"

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    @property
    def last_duration_s(self) -> float:
        return self._last_duration_s

    @property
    def last_rms(self) -> float:
        return self._last_rms

    @property
    def active_input_device_label(self) -> str:
        return self._active_input_device_label

    def start(self) -> None:
        if self._stream is not None:
            return
        self._chunks.clear()
        self._last_duration_s = 0.0
        self._last_rms = 0.0
        self._active_input_device = None
        self._active_input_device_label = "unknown"

        def _callback(indata: np.ndarray, frames: int, time_info: dict, status) -> None:
            del frames, time_info
            if status:
                # Keep the stream alive even if occasional status is present.
                pass
            self._chunks.append(indata.copy())

        sample_rates = [float(self.sample_rate), self._default_input_sample_rate()]
        # De-duplicate while keeping order.
        unique_rates: list[float] = []
        for rate in sample_rates:
            if rate not in unique_rates:
                unique_rates.append(rate)

        last_exc: sd.PortAudioError | None = None
        for sample_rate in unique_rates:
            for retry in range(3):
                try:
                    self._stream = self._open_input_stream(_callback, sample_rate=sample_rate)
                    self._stream.start()
                    self._active_sample_rate = float(sample_rate)
                    return
                except sd.PortAudioError as exc:
                    last_exc = exc
                    if not self._is_recoverable_portaudio_error(exc):
                        raise
                    self._reset_portaudio()
                    time.sleep(0.2 + (retry * 0.1))
                    continue

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Failed to open input stream.")

    def _open_input_stream(self, callback, sample_rate: float):
        device_index = self._select_input_device_index()
        self._active_input_device = device_index
        self._active_input_device_label = self._describe_input_device(device_index)
        return sd.InputStream(
            samplerate=sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=callback,
            device=device_index,
        )

    def _default_input_sample_rate(self) -> float:
        try:
            device_index = self._select_input_device_index()
            device_info = sd.query_devices(device_index)
            if isinstance(device_info, dict):
                value = device_info.get("default_samplerate")
                if value:
                    return float(value)
        except Exception:
            pass
        return float(self.sample_rate)

    def _select_input_device_index(self) -> int | None:
        try:
            devices = sd.query_devices()
            if not isinstance(devices, (list, tuple)):
                return None
        except Exception:
            return None

        built_in_keywords = (
            "macbook pro microphone",
            "built-in microphone",
            "internal microphone",
            "内建麦克风",
        )
        for idx, info in enumerate(devices):
            try:
                channels = int(info.get("max_input_channels", 0))
                name = str(info.get("name", "")).lower()
            except Exception:
                continue
            if channels > 0 and any(keyword in name for keyword in built_in_keywords):
                return idx

        try:
            default_pair = sd.default.device
            if isinstance(default_pair, (list, tuple)) and len(default_pair) >= 1:
                default_input = int(default_pair[0])
                if default_input >= 0:
                    info = sd.query_devices(default_input)
                    if int(info.get("max_input_channels", 0)) > 0:
                        return default_input
        except Exception:
            pass

        for idx, info in enumerate(devices):
            try:
                if int(info.get("max_input_channels", 0)) > 0:
                    return idx
            except Exception:
                continue
        return None

    def _describe_input_device(self, device_index: int | None) -> str:
        if device_index is None:
            return "system-default"
        try:
            info = sd.query_devices(device_index)
            name = str(info.get("name", "")).strip() or f"#{device_index}"
            return f"{name} (#{device_index})"
        except Exception:
            return f"#{device_index}"

    def _is_recoverable_portaudio_error(self, exc: sd.PortAudioError) -> bool:
        message = str(exc).lower()
        return (
            "-10851" in message
            or "invalid property value" in message
            or "auhal" in message
            or "!obj" in message
        )

    def _reset_portaudio(self) -> None:
        terminate = getattr(sd, "_terminate", None)
        initialize = getattr(sd, "_initialize", None)
        if callable(terminate):
            try:
                terminate()
            except Exception:
                pass
        if callable(initialize):
            try:
                initialize()
            except Exception:
                pass

    def stop_and_dump_wav(self) -> Path:
        if self._stream is None:
            raise RuntimeError("Recorder is not running.")

        self._stream.stop()
        self._stream.close()
        self._stream = None

        if not self._chunks:
            raise RuntimeError("No audio captured.")

        audio = np.concatenate(self._chunks, axis=0)
        frames = int(audio.shape[0]) if audio.ndim >= 1 else 0
        self._last_duration_s = (
            float(frames) / float(self._active_sample_rate)
            if self._active_sample_rate > 0
            else 0.0
        )
        if audio.size > 0:
            self._last_rms = float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))
        else:
            self._last_rms = 0.0
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        path = Path(tmp.name)
        tmp.close()
        sf.write(path, audio, int(round(self._active_sample_rate)))
        self._chunks.clear()
        return path
