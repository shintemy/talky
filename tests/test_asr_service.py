from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf


def _load_asr_service_with_fake_mlx(transcribe_impl):
    fake_mlx = types.SimpleNamespace(transcribe=transcribe_impl)
    sys.modules["mlx_whisper"] = fake_mlx
    sys.modules.pop("talky.asr_service", None)
    return importlib.import_module("talky.asr_service")


def _write_dummy_wav(path: Path) -> None:
    audio = np.zeros(1600, dtype=np.float32)
    sf.write(path, audio, 16000)


def test_transcribe_resolves_relative_model_path_to_absolute(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    model_dir = tmp_path / "local_whisper_model"
    model_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    wav_file = tmp_path / "audio.wav"
    _write_dummy_wav(wav_file)

    captured: dict[str, str] = {}

    def transcribe_impl(audio_input, **kwargs):  # noqa: ANN001, ANN003
        del audio_input
        captured["model_ref"] = kwargs["path_or_hf_repo"]
        return {"text": "ok"}

    asr_service = _load_asr_service_with_fake_mlx(transcribe_impl)
    asr = asr_service.MlxWhisperASR(model_name="./local_whisper_model", language="zh")

    result = asr.transcribe(wav_file, initial_prompt="")

    assert result == "ok"
    assert captured["model_ref"] == str(model_dir.resolve())


def test_transcribe_raises_clear_error_for_missing_local_model_path(tmp_path: Path) -> None:
    def transcribe_impl(_audio_input, **_kwargs):  # noqa: ANN001, ANN003
        raise AssertionError("mlx_whisper.transcribe should not be called for missing local path")

    asr_service = _load_asr_service_with_fake_mlx(transcribe_impl)
    asr = asr_service.MlxWhisperASR(model_name="/local_whisper_model", language="zh")

    with pytest.raises(FileNotFoundError, match="Whisper model path not found"):
        asr.transcribe(tmp_path / "audio.wav", initial_prompt="")
